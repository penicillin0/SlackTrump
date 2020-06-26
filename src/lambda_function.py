import json
import os
import urllib.request
import random
import boto3
import datetime


def lambda_handler(event, context):

    ####################
    ### ここから各種検証 ###

    # リトライイベントなら終了
    if reserchTimeoutOrNot(event):
        return {'statusCode': 200, 'body': json.dumps('retry')}

    body = json.loads(event['body'])

    # トークンを検証
    token = body['token']
    if token != os.environ['SLACK_TOKEN']:
        return {'statusCode': 200, 'body': json.dumps('bad token')}

    # botなら終了
    if 'user' not in body['event'].keys():
        return {'statusCode': 200, 'body': json.dumps('not user')}
    else:
        userID = body['event']['user']
        userName = os.environ[userID]

    text = body['event']['text']

    # 有効なテキストが入っていないなら終了
    if not checkValidText(text):
        return {'statusCode': 200, 'body': json.dumps('valid text')}

    ### ここまで各種検証 ###
    ####################

    # dynamodbのアカウントとか
    client = boto3.client('dynamodb')
    d_today = str(datetime.date.today()).replace('-', '')
    primary_key = {"date": {"S": d_today}}
    item = client.get_item(TableName='TrumpHistory', Key=primary_key)

    text = body['event']['text']
    # 削除なら削除して終了
    if "delete" in text:
        format_DB(d_today, client)
        return {'statusCode': 200, 'body': json.dumps('delete')}

    if "Item" in item.keys():
        trumpinfo = item['Item']['trump']["L"]
    else:
        trumpinfo = []

    # 重複を削除
    trumpinfo_wo_daburi, drawn_trump_set = resolveOverlap(trumpinfo)

    # トランプ全部
    all_trump = createAllTrump()

    # トランプを引く
    all_trump_set = set(all_trump)
    able_draw_list = list(all_trump_set - drawn_trump_set)
    draw_trump = random.choice(able_draw_list)

    # 引いたトランプを加える
    trumpinfo_wo_daburi.append({'S': draw_trump})
    drawnTrumpNum = len(trumpinfo_wo_daburi)
    remainTrumpNum = 52 - len(trumpinfo_wo_daburi)

    append_item = {
        "date": {
            "S": d_today
        },
        "trump": {
            "L": trumpinfo_wo_daburi
        }
    }

    client.put_item(TableName='TrumpHistory', Item=append_item)

    if 'トランプ' in text:
        rep = draw_trump.replace('d', '♦').replace('h', '♥').replace(
            'k', '♣').replace('s', '♠').replace('j', ':black_joker:')

        post_message_to_channel(
            "ーーーーー\n" +
            "{:13}".format('|'+rep)+'|\n' +
            "{:8}".format('|'+userName+'さん')+'|'+'\n' +
            "{:11}".format('|')+rep+'|\n' +
            "ーーーーー\n\n"
            'カードの残り枚数:'+str(remainTrumpNum)+'\n\n' +
            '引かれたカードの枚数:'+str(drawnTrumpNum)+'\n\n')
        # 'DB確認用(後で消す)'+'\n'+
        # '------------------'+'\n'+
        # json.dumps(append_item))

    return {'statusCode': 200, 'body': json.dumps('ok')}


def post_message_to_channel(message):
    url = os.environ['SLACK_WEBHOOK_URL']
    data = {
        "text": message,
    }

    req = urllib.request.Request(url, data=json.dumps(
        data).encode("utf-8"), method="POST")
    urllib.request.urlopen(req)


def format_DB(d_today, client):
    clear_item = {
        "date": {
            "S": d_today
        },
        "trump": {
            "L": []
        }
    }
    client.put_item(TableName='TrumpHistory', Item=clear_item)
    post_message_to_channel(str(d_today)+"のDBをクリアしました")


def reserchTimeoutOrNot(event):
    if 'x-slack-retry-reason' in event['headers']:
        if event['headers']['x-slack-retry-reason'] in ['http_error', 'http_timeout']:
            # 確認用
            # post_message_to_channel("以下の理由で要求を棄却しました"+event['headers']['x-slack-retry-reason'])
            return True
    return False


def createAllTrump():
    all_trump = []
    for i in range(1, 14):
        for kigou in ['d', 's', 'h', 'k']:
            all_trump.append(kigou + str(i))
    all_trump.append('j1')
    all_trump.append('j2')
    return all_trump


def checkValidText(text):
    boolean = False
    validTextList = ['トランプ', 'delete']
    for validText in validTextList:
        if validText in text:
            return True
    return False


def resolveOverlap(trumpinfo):
    # trumpinfo -> trumpinfo_wo_dauri
    drawn_trump_list = []
    trumpinfo_wo_daburi = []
    for trump in trumpinfo:
        if trump["S"] not in drawn_trump_list:
            drawn_trump_list.append(trump["S"])
            trumpinfo_wo_daburi.append(trump)
    drawn_trump_set = set(drawn_trump_list)
    return trumpinfo_wo_daburi, drawn_trump_set
