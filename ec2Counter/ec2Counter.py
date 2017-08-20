import os
import sys
import json
import boto3
from datetime import datetime
import request

ec2_tag_key = os.environ['EC2_TAG_KEY']
ec2_tag_value = os.environ['EC2_TAG_VALUE']
service = ec2_tag_key + '_' + ec2_tag_value
read_capacity_per_instance = os.environ['READ_CAPACITY_PER_INSTANCE']
write_capacity_per_instance = os.environ['WRITE_CAPACITY_PER_INSTANCE']
dynamodb_tables = os.environ['DYNAMODB_TABLES'].split(',')

# encrypted_slack_endpoint = os.environ['SLACK_ENDPOINT']
# slack_endpoint = 'https://' + kms.decrypt(CiphertextBlob=b64decode(encrypted_slack_endpoint))['Plaintext'].decode('utf-8')
# slack_channel = os.environ['SLACK_CHANNEL']
# slack_username = os.environ['SLACK_USERNAME']
# slack_icon_emoji = os.environ['SLACK_ICON_EMOJI'

def ec2():
    """
     - Overview
     - Description
     - Environment variable
     - Argument
     - Response
    """

    # for debug
    # return boto3.client('ec2', endpoint_url='http://127.0.0.1:3001/')
    return boto3.client('ec2', region_name='ap-northeast-1')

def dynamodb():
    """
     - Overview
     - Description
     - Environment variable
     - Argument
     - Response
    """

    # for debug
    # return boto3.client('dynamodb', endpoint_url='http://127.0.0.1:8000/')
    return boto3.client('dynamodb', region_name='ap-northeast-1')

def http_request(url, method, headers, payload):
    """
     - Overview
       - 汎用的な HTTP リクエストを処理する
     - Description
       - 汎用的な HTTP リクエストを処理する
     - Environment variable
       - None
     - Argument
       - url
       - method
       - headers
       - payload
     - Response
       - None
    """

    if method == 'POST':
        try:
            response = requests.post(url, headers=headers, data=payload, verify=False)
        except Exception as e:
            print(e)
    elif method == 'DELETE':
        try:
            response = requests.delete(url, headers=headers, verify=False)
        except Exception as e:
            print(e)

    if response.status_code == '200':
        print('Message sent successfully.')
    else:
        print('Message sent unsuccessfully.')

def notify(message):
    """
     - Overview
       - Slack channel にメッセージを投稿する
     - Description
       - Slack channel にメッセージを投稿する
     - Environment variable
       - None
     - Argument
       - message
     - Response
       - None
    """

    print(message)

    # slack_message = {
    #     'channel': slack_channel,
    #     'username': slack_username,
    #     'icon_emoji': slack_icon_emoji,
    #     'text': "%s" % (message)
    # }

    # headers = {
    #   "User-Agent": "ec2Ctrl",
    # }
    # print(slack_message)
    # http_request(slack_endpoint, 'POST', headers, json.dumps(slack_message))

def count_ec2_instances():
    """
     - Overview
       - タグで指定した EC2 インスタンス数をカウントする
     - Description
       - タグで指定した EC2 インスタンス数をカウントする
     - Environment variable
       - EC2_TAG_KEY   ... カウントする EC2 のタグ Key
       - EC2_TAG_VALUE ... カウントする EC2 のタグ Value
     - Argument
       - None
     - Response
       - ec2_num(int)
    """

    try:
        response = ec2().describe_instances(
            Filters=[
                {
                    'Name': 'tag-key',
                    'Values': [ec2_tag_key]
                },
                {
                    'Name': 'tag-value',
                    'Values': [ec2_tag_value]
                },
                {
                    'Name': 'instance-state-name',
                    'Values': ['running']
                }
            ]
        )
    except Exception as e:
        notify('インスタンス一覧の取得に失敗しました.' + str(e))

    ec2_num = len(response['Reservations'])
    return ec2_num

def store_ec2_count_number(ec2_num):
    """
     - Overview
       - EC2 の台数を DynamoDB に書き込む
     - Description
       - EC2 の台数を DynamoDB に書き込む
       - Table Name: Ec2Counter
     - Environment variable
       - None
     - Argument
       - ec2_num
     - Response
       - None
    """

    update_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        response = dynamodb().put_item(
            TableName='Ec2Counter',
            Item={
                "Service": {"S": service},
                "Count": {"N": str(ec2_num)},
                "UpdateAt": {"S": update_at}
            }
        )
    except Exception as e:
        notify('インスタンス数の書き込みに失敗しました.' + str(e))

def select_ec2_count_number():
    """
     - Overview
       - EC2 の台数を DynamoDB から取得する
     - Description
       - EC2 の台数を DynamoDB から取得する
       - Table Name: Ec2Counter
     - Environment variable
       - None
     - Argument
       - None
     - Response
       - stored_ec2_num(int)
    """

    try:
        response = dynamodb().get_item(
            TableName='Ec2Counter',
            Key={
                "Service": {"S": service},
            }
        )
    except Exception as e:
        notify('インスタンス数の取得に失敗しました.' + str(e))

    stored_ec2_num = response['Item']['Count']['N']
    return stored_ec2_num

def comparison_ec2_count_number(current_value, stored_value):
    """
     - Overview
       - EC2 台数増減をチェックする
     - Description
       - EC2 台数増減をチェックして unchanged | increased | decreased の何れかを返却する
     - Environment variable
       - None
     - Argument
       - current_value ... 現在の EC2 台数
       - stored_value  ... 直近の EC2 台数（DynamoDB より取得）
     - Response
       - result(string)
    """

    result = ""
    if current_value == stored_value:
        result = "unchanged"
    elif current_value > stored_value:
        notify('インスタンス数が増加しました. ' + str(stored_value) + ' → ' + str(current_value) + ' Provisioned Capacity Unit の追加を行います.')
        result = "increased"
    elif current_value < stored_value:
        notify('インスタンス数が減少しました. ' + str(stored_value) + ' → ' + str(current_value) + ' Provisioned Capacity Unit の縮退を行います.')
        result = "decreased"

    return result

def calculate_dynamodb_capacity(ec2_num):
    """
     - Overview
       - EC2 の台数から DynamoDB のキャパシティを算出する
     - Description
       - EC2 の台数 x WRITE_CAPACITY_PER_INSTANCE
       - EC2 の台数 x READ_CAPACITY_PER_INSTANCE
     - Environment variable
       - READ_CAPACITY_PER_INSTANCE  ... EC2 1 台あたりの読み込みキャパシティ
       - WRITE_CAPACITY_PER_INSTANCE ... EC2 1 台あたりの書き込みキャパシティ
     - Argument
       - ec2_num
     - Response
       - read_capacity(int)
       - write_capacity(int)
    """

    read_capacity = int(ec2_num) * int(read_capacity_per_instance)
    write_capacity = int(ec2_num) * int(write_capacity_per_instance)

    return read_capacity, write_capacity

def run(event, context):
    """
     - Overview
       - 指定したタグの EC2 の台数をカウントする
     - Description
       - 指定したタグの EC2 の台数をカウントする
     - Environment variable
       - None
     - Argument
       - None
     - Response
       - output(json)
    """

    # EC2 の台数をカウントする
    current_ec2_num = count_ec2_instances()
    output = {}
    if current_ec2_num != 0:
        # 直近の EC2 の台数を DynamoDB より取得する
        stored_ec2_num = select_ec2_count_number()

        # EC2 台数の増減をチェック
        comparison_result = comparison_ec2_count_number(int(current_ec2_num), int(stored_ec2_num))

        # EC2 の台数から想定する DynamoDB キャパシティを算出する
        read_capacity, write_capacity = calculate_dynamodb_capacity(current_ec2_num)

        output['ec2_num_status'] = comparison_result # unchanged(変化無し) increased(増加) decreased(減少)
        output['ec2_num_count'] = current_ec2_num
        tables = []
        for dynamodb_table in dynamodb_tables:
            table = {}
            table['name'] = dynamodb_table
            capacity_unit = {}
            capacity_unit['read_capacity_units'] = read_capacity
            capacity_unit['write_capacity_units'] = write_capacity
            table['capacity_unit'] = capacity_unit
            tables.append(table)

        # 最新の EC2 の台数を DynamoDB に書き込む
        store_ec2_count_number(current_ec2_num)
        output['tables'] = tables
    else:
        output['ec2_num_status'] = "unchanged"
        notify('カウント対象のインスタンスが存在していません.')

    return output

# if __name__ == '__main__':
#     run('', '')
