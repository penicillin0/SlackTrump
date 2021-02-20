import json
import os
import urllib.request
import random
import boto3
import datetime

TOTAL_TRUMP_NUM: int = 54


def lambda_handler(event, context):

    ########################
    ### ここから各種検証 ###

    # リトライイベントなら終了
    if is_reserch_timeout(event):
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
    if not is_valid_text(text):
        return {'statusCode': 200, 'body': json.dumps('valid text')}

    ### ここまで各種検証 ###
    ########################

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
    trumpinfo_wo_daburi, drawn_trump_set = resolve_overlap(trumpinfo)

    # トランプ全部
    all_trump = create_all_trump()

    # トランプを引く
    all_trump_set = set(all_trump)
    able_draw_list = list(all_trump_set - drawn_trump_set)
    draw_trump = random.choice(able_draw_list)

    # jokerの枚数をチェック
    joker_num_nokori = get_joker_num(able_draw_list)
    if draw_trump == 'j1' or draw_trump == 'j2':
        joker_num_nokori -= 1

    # 引いたトランプを加える
    trumpinfo_wo_daburi.append({'S': draw_trump})
    drawn_trump_num = len(trumpinfo_wo_daburi)
    remain_trump_num = TOTAL_TRUMP_NUM - len(trumpinfo_wo_daburi)

    append_item = {
        "date": {
            "S": d_today
        },
        "trump": {
            "L": trumpinfo_wo_daburi
        }
    }

    client.put_item(TableName='TrumpHistory', Item=append_item)

    if ('トランプ' in text) or ('とらんぷ' in text) or ('Trump' in text) or ('trump' in text):
        rep = draw_trump.replace('d', '♦').replace('h', '♥').replace(
            'k', '♣').replace('s', '♠').replace('j', ':black_joker:')

        post_message_to_channel(
            "ーーーーー\n" +
            "{:13}".format('|'+rep)+'|\n' +
            "{:8}".format('|'+userName+'さん')+'|'+'\n' +
            "{:11}".format('|')+rep+'|\n' +
            "ーーーーー\n\n"
            ':トランプ:の残り枚数:'+str(remain_trump_num)+'\n\n\n\n' +
            '引かれた:トランプ:の枚数:'+str(drawn_trump_num)+'\n\n' +
            '引かれた:black_joker:の枚数:'+str(2 - joker_num_nokori)+'\n\n'
        )
        # 'DB確認用(後で消す)'+'\n'+
        # '------------------'+'\n'+
        # json.dumps(append_item))

    return {'statusCode': 200, 'body': json.dumps('ok')}


def get_joker_num(trump_list):
    joker_num = 0
    for trump in trump_list:
        if 'j' in trump:
            joker_num += 1
    return joker_num


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


def is_reserch_timeout(event):
    if 'x-slack-retry-reason' in event['headers']:
        if event['headers']['x-slack-retry-reason'] in ['http_error', 'http_timeout']:
            # 確認用
            # post_message_to_channel("以下の理由で要求を棄却しました"+event['headers']['x-slack-retry-reason'])
            return True
    return False


def create_all_trump():
    all_trump = []
    for i in range(1, 14):
        for kigou in ['d', 's', 'h', 'k']:
            all_trump.append(kigou + str(i))
    all_trump.append('j1')
    all_trump.append('j2')
    return all_trump


def is_valid_text(text):
    validTextList = ['トランプ', 'delete', 'とらんぷ', 'Trump', 'trump']
    for validText in validTextList:
        if validText in text:
            return True
    return False


def resolve_overlap(trumpinfo):
    # trumpinfo -> trumpinfo_wo_dauri
    drawn_trump_list = []
    trumpinfo_wo_daburi = []
    for trump in trumpinfo:
        if trump["S"] not in drawn_trump_list:
            drawn_trump_list.append(trump["S"])
            trumpinfo_wo_daburi.append(trump)
    drawn_trump_set = set(drawn_trump_list)
    return trumpinfo_wo_daburi, drawn_trump_set
