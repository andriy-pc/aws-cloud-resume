import hashlib

import boto3
from botocore.exceptions import ClientError
import json

# DynamoDB table
TABLE_NAME = "visitors_tracker"
PRIMARY_KEY = "id"
VISITORS_KEY = "visitors_count"


dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)

EXPECTED_HASH = "7cfda390e7591d24e1f8be117d995c65c0d3ed015fb78b7a861d13b582049996"

def lambda_handler(event, context):
    header_value = event['headers'].get('X-API-Key', '')
    received_hash = hashlib.sha256(header_value.encode()).hexdigest()
    if received_hash != EXPECTED_HASH:
        return {"statusCode": 403, "body": "Forbidden"}
    try:
        response = table.update_item(
            Key={PRIMARY_KEY: "visitors_count"},
            UpdateExpression=f"SET {VISITORS_KEY} = if_not_exists({VISITORS_KEY}, :start) + :inc",
            ExpressionAttributeValues={
                ':inc': 1,
                ':start': 0
            },
            ReturnValues="UPDATED_NEW"
        )

        new_count = response['Attributes'][VISITORS_KEY]
        return {
            'statusCode': 200,
            'body': json.dumps({
                'visitors_count': int(new_count)
            })
        }

    except ClientError as e:
        return {
            'statusCode': 500,
            'body': f"Error updating visitors count: {e.response['Error']['Message']}"
        }
    except Exception:
        return {
            'statusCode': 500,
            'body': f"Error updating visitors count"
        }