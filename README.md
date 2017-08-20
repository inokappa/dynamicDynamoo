# dynamicDynamoo

[toc]

## なにこれ

* EC2 の台数をベースにして DynamoDB の Provisioned capacity を自動的に上げ下げする試み
* 既に [DynamoDB は Provisioned capacity の Auto Scaling をサポートしている](https://aws.amazon.com/jp/blogs/news/new-auto-scaling-for-amazon-dynamodb/)が、それとは違ったパラメータで Auto Scaling させてみたい
* なんちゃって Auto Scaling を目指す
* Lambda と DynamoDB そして StepFunctions を利用する
* dynamicDynamoo はディスカウントストア「[ダイクマ](https://www.youtube.com/watch?v=zGPbX4I27Cs)」へのオマージュです

## 構成

### 図

![構成図](https://raw.githubusercontent.com/wiki/inokappa/dynamicDynamoo/images/2017082002.png)

### 役割

| Lambda Function | 役割 | 詳細 | 備考 |
|:---|:---|:---|
| ec2Counter | カウント用 Lambda Function | タグで指定した EC2 インスタンスの数をカウントして DynamoDB に記録する | DynamoDB Table Ec2Counter を利用する |
| capacityScaler | Capacity 調整用 Lambda Function | Provisioned capacity を変更する | EC2 の増減に一応対応している |

これらの Lambda Function を StepFunctions でつなぐ。

### StepFunctions ビジュアルワークフロー

![ビジュアルワークフロー](https://raw.githubusercontent.com/wiki/inokappa/dynamicDynamoo/images/2017082001.png)

## 始め方

### 有ると良いもの

- [Serverless Framework](https://github.com/serverless/serverless)

### ec2Counter

#### serverless.yml を修正

```sh
cd ec2Counter
vim serverless.yml
```

`environment` あたりを環境に合わせて修正する。

```yaml
...
environment:
  EC2_TAG_KEY: "app"
  EC2_TAG_VALUE: "web"
  READ_CAPACITY_PER_INSTANCE: 1
  WRITE_CAPACITY_PER_INSTANCE: 1
  DYNAMODB_TABLES: "aaa,bbb" # Provisioned capacity を調整したい DynamoDB テーブルをカンマ区切りで指定する
...
```

#### 後は Deploy

```sh
sls deploy
```

### capacityScaler

#### deploy

```sh
cd capacityScaler
sls deploy
```

### StepFunctions ASL

```json
{
  "Comment": "dynamicDynamoo",
  "StartAt": "ec2Counter",
  "States": {
    "ec2Counter": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:ap-northeast-1:xxxxxxxxxxxxx:function:ec2Counter-env-Counter",
      "Next": "ec2_number_status_change?"
    },
    "ec2_number_status_change?": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.ec2_num_status",
          "StringEquals": "increased",
          "Next": "capacityScaler"
        },
        {
          "Variable": "$.ec2_num_status",
          "StringEquals": "decreased",
          "Next": "capacityScaler"
        },
        {
          "Variable": "$.ec2_num_status",
          "StringEquals": "unchanged",
          "Next": "Do_Nothing"
        }
      ],
      "Default": "Do_Nothing"
    },
    "capacityScaler": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:ap-northeast-1:xxxxxxxxxxxxx:function:capacityScaler-dev-Scaler",
      "End": true
    },
    "Do_Nothing": {
      "Type": "Pass",
      "End": true
    }
  }
}

```

## 課題

* EC2 台数が減って Capacity を減らす場合のロジックを詰める必要がある
* 複数のテーブルを扱うことが出来るが、テーブルで Capacity が異なる場合には個々に StepFunctions ステートマシンを用意する必要がある...
* 処理に失敗した際等の Slack 通知を有効化（今はコメントアウト）したい
* StepFunctions のステートマシンを実行するトリガについて要検討（CloudWatch Events を検討中）
* StepFunctions のデプロイも Serverless Framework でやりたい

## その他

### 注意

* serverless.yml 内の各種パラメータについては、環境に応じて適宜変更すること
* あくまでもサンプル実装なので本番環境での利用は十分に検証を行うこと
