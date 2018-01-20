import os
import time
import feedparser
import boto3
import requests

HOOK_URL = os.environ['BOT_URL']
TABLE_NAME = os.environ['TABLE_NAME']
DB = boto3.resource('dynamodb')
FEEDS = [
    'https://aws.amazon.com/new/feed/',
    'https://aws.amazon.com/security/security-bulletins/feed/'
]

def check_items(keys, items):
    if len(keys) > 0:
        response = DB.batch_get_item(
            RequestItems={TABLE_NAME: {'Keys': keys}},
            ReturnConsumedCapacity='TOTAL'
        )
        keys = []
        print('DynamoDB read capacity used: ', response['ConsumedCapacity'])

        if 'Responses' in response:
            for item in response['Responses'][TABLE_NAME]:
                del items[item['id']]

    return items

def commit_items(dynamodb_items):
    print("DynamoDB Items:", dynamodb_items)
    if len(dynamodb_items) != 0:
        response = DB.batch_write_item(
            RequestItems={
                TABLE_NAME: dynamodb_items
            },
            ReturnConsumedCapacity='TOTAL'
        )
        print('DynamoDB write capacity used: ', response['ConsumedCapacity'])

def load_new_items():
    items = {}
    for feed in FEEDS:
        print(feed)
        news_feed = feedparser.parse(feed)
        keys = []

        epoch_time = int(time.time()) + 2592000
        for entry in news_feed['entries']:
            id = entry['title_detail']['value'].lower()
            keys.append({'id': id})
            items[id] = {
                'id': id,
                'expire': epoch_time,
                'message': entry['title_detail']['value'] + ': ' +  entry['link']
            }
            if len(keys) == 20:
                items = check_items(keys, items)
                keys = []

        if len(keys) != 20:
            items = check_items(keys, items)

    dynamodb_items = []
    for __, value in items.items():
        dynamodb_items.append({'PutRequest': {'Item': value}})
        if len(dynamodb_items) == 20:
            commit_items(dynamodb_items)
            dynamodb_items = []
    commit_items(dynamodb_items)
    return items


def lambda_handler(event, context):
    new_messages = load_new_items()
    content = ""
    if len(new_messages) >= 20:
        response = requests.post(url=HOOK_URL, json={"Content": "Too many new messages... Check the site: https://aws.amazon.com/new. "})
        print(response)
        return
    for __, message in new_messages.items():
        content = message['message']
        response = requests.post(url=HOOK_URL, json={"Content": content})

    print(content)
