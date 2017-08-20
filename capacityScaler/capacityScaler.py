import os
import sys
import json
import boto3
import datetime
import requirements
from pytz import timezone

# encrypted_slack_endpoint = os.environ['SLACK_ENDPOINT']
# slack_endpoint = 'https://' + kms.decrypt(CiphertextBlob=b64decode(encrypted_slack_endpoint))['Plaintext'].decode('utf-8')
# slack_channel = os.environ['SLACK_CHANNEL']
# slack_username = os.environ['SLACK_USERNAME']
# slack_icon_emoji = os.environ['SLACK_ICON_EMOJI'

def dynamodb():
    """
     - Overview
       - DynamoDB クライアントの初期化
     - Description
       - DynamoDB クライアントの初期化
       - Region べた書きごめんくさい
     - Environment variable
       - None
     - Argument
       - None
     - Response
       - boto3.client
    """
    # return boto3.client('dynamodb', endpoint_url='http://127.0.0.1:8000/')
    return boto3.client('dynamodb', region_name='ap-northeast-1')

def cloudwatch():
    """
     - Overview
       - CloudWatch クライアントの初期化
     - Description
       - CloudWatch クライアントの初期化
     - Environment variable
       - None
     - Argument
       - None
     - Response
       - boto3.client
    """
    return boto3.client('cloudwatch', region_name='ap-northeast-1')

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

    slack_message = {
        'channel': slack_channel,
        'username': slack_username,
        'icon_emoji': slack_icon_emoji,
        'text': "%s" % (message)
    }

    headers = {
      "User-Agent": "ec2Ctrl",
    }
    print(slack_message)
    # http_request(slack_endpoint, 'POST', headers, json.dumps(slack_message))

def scale_dynamodb_provisioned_capacity_units(dynamodb_table, read_capacity, write_capacity):
    """
     - Overview
       - DynamoDB の ProvisionedThroughput を更新する
     - Description
       - DynamoDB の ProvisionedThroughput を更新する
     - Environment variable
       - None
     - Argument
       - dynamodb_table
       - read_capacity
       - write_capacity
     - Response
       - None
    """

    print(dynamodb_table + ' の Provisioned Capacity を変更します.')
    try:
        response = dynamodb().update_table(
            TableName=dynamodb_table,
            ProvisionedThroughput={
                'ReadCapacityUnits': int(read_capacity),
                'WriteCapacityUnits': int(write_capacity)
            }
        )
        print(dynamodb_table + ' の Provisioned Capacity を変更しました.')
    except Exception as e:
        print(dynamodb_table + ' の Provisioned Capacity を変更に失敗しました.' + str(e))
        sys.exit(1)

def get_dynamodb_provisioned_capacity_units(dynamodb_table):
    """
     - Overview
       - DynamoDB の Provisioned キャパシティを取得する
     - Description
       - DynamoDB の Provisioned キャパシティを取得する
     - Environment variable
       - None
     - Argument
       - dynamodb_table
     - Response
       - provisioned_read_capacity
       - provisioned_write_capacity
    """

    try:
        response = dynamodb().describe_table(
            TableName=dynamodb_table
        )
    except Exception as e:
        print(e)

    provisioned_read_capacity = response['Table']['ProvisionedThroughput']['ReadCapacityUnits']
    provisioned_write_capacity = response['Table']['ProvisionedThroughput']['WriteCapacityUnits']

    return provisioned_read_capacity, provisioned_write_capacity

def get_dynamodb_consumed_capacity_units(dynamodb_table):
    """
     - Overview
       - DynamoDB の Consumed キャパシティを CloudWatch から取得する
     - Description
       - DynamoDB の Consumed キャパシティを CloudWatch から取得する
     - Environment variable
       - None
     - Argument
       - dynamodb_table
     - Response
       - consumed_read_capacity
       - consumed_write_capacity
    """

    consumed_read_capacity = ""
    consumed_write_capacity = ""

    metrics = ['ConsumedReadCapacityUnits', 'ConsumedWriteCapacityUnits']
    for metric in metrics:
        try:
            response = cloudwatch().get_metric_statistics(
                Namespace='AWS/DynamoDB',
                MetricName=metric,
                Dimensions=[
                    {
                        'Name': 'TableName',
                        'Value': dynamodb_table
                    }
                ],
                StartTime=datetime.datetime.now(timezone('UTC')) - datetime.timedelta(seconds=180),
                EndTime=datetime.datetime.now(timezone('UTC')),
                Period=60,
                Statistics=['Maximum'],
                Unit='Count'
            )
            if len(response['Datapoints']) > 0:
                if metric == 'ConsumedReadCapacityUnits':
                    consumed_read_capacity = int(response['Datapoints'][-1]['Maximum'])
                elif metric == 'ConsumedWriteCapacityUnits':
                    consumed_write_capacity = int(response['Datapoints'][-1]['Maximum'])
            else:
                # CloudWatch の Datapoints が無い場合には暫定的に 0 を返す
                if metric == 'ConsumedReadCapacityUnits':
                    consumed_read_capacity = 0
                elif metric == 'ConsumedWriteCapacityUnits':
                    consumed_write_capacity = 0
        except Exception as e:
            print(e)

    return consumed_read_capacity, consumed_write_capacity

def capacity_unit_update_check(provisioned_value, consumed_value, update_value):
    """
     - Overview
       - current_value と update_value を比較して Provisioned Capacity の更新可不可を返す
     - Description
       - current_value と update_value を比較して Provisioned Capacity の更新可不可を返す
     - Environment variable
       - None
     - Argument
       - provisioned_value
       - consumed_value
       - update_value
     - Response
       - true  ... 更新可
       - false ... 更新不
    """

    # Provisioned Capacity から Consumed Capacity の差分を取得
    v = provisioned_value - consumed_value
    # 更新したい Provisioned Capacity を 2 倍する
    u = update_value * 2

    # Provisioned Capacity から Consumed Capacity の差分が、
    # 更新したい Provisioned Capacity を 2 倍した数値よりも大きい場合には更新する
    if int(v) > int(u):
        return True
    elif int(v) < int(u):
        return False
    elif int(v) == int(u):
        return False

def run(event, context):
    """
     - Overview
       - ec2Counter の結果を解析して Provisioned Capacity を変更する
     - Description
       - ec2Counter の結果を解析して Provisioned Capacity を変更する
     - Environment variable
       - None
     - Argument
       - event
     - Response
       - None
    """

    if event['ec2_num_status'] != 'unchanged':
        for t in event['tables']:
            new_read_capacity_units = t['capacity_unit']['read_capacity_units']
            new_write_capacity_units = t['capacity_unit']['write_capacity_units']

            # Provisioned Read Capcity と Provisioned Write Capacity を取得する
            provisioned_read_capacity, provisioned_write_capacity = get_dynamodb_provisioned_capacity_units(t['name'])
            # Consumed Read Capcity と Consumed Write Capacity を取得する
            consumed_read_capacity, consumed_write_capacity = get_dynamodb_consumed_capacity_units(t['name'])

            # インスタンスが追加された場合
            if event['ec2_num_status'] == 'increased':
                # インスタンスが追加された場合には問答無用に Provisioned Capacity を更新する
                scale_dynamodb_provisioned_capacity_units(t['name'], new_read_capacity_units, new_write_capacity_units)
            # インスタンスが削除された場合
            elif event['ec2_num_status'] == 'decreased':
                # EC2 が削除された場合には、
                # CloudWatch から Consumed Capacity を取得し、Provisioned Capacity の値と比較し、
                # Consumed Capacity よりも Provisioned Capacity が低い値にならないように対処している
                is_update_read_capacity = capacity_unit_update_check(
                    provisioned_read_capacity,
                    consumed_read_capacity,
                    new_read_capacity_units
                )
                is_update_write_capacity = capacity_unit_update_check(
                    provisioned_write_capacity,
                    consumed_write_capacity,
                    new_write_capacity_units
                )
                # is_update_read_capacity 又は is_update_read_capacity が true であれば更新する
                if is_update_read_capacity or is_update_write_capacity:
                    scale_dynamodb_provisioned_capacity_units(t['name'], new_read_capacity_units, new_write_capacity_units)
                else:
                    print(t['name'] + ' の構成変更の条件が満たされないので Provisioned Capacity の変更は行いません.')
    else:
        print('EC2 構成に変更が無い為、Provisioned Capacity の変更は行いません.')
