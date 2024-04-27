from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    ShowLoadingAnimationRequest
)
import json
import os
import requests
from PIL import Image
from io import BytesIO
from firebase import firebase
import google.generativeai as genai


# 使用環境變量讀取憑證
secret = os.getenv('LINE_CHANNEL_SECRET', None)
token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None)
firebase_url = os.getenv('FIREBASE_URL')
gemini_key = os.getenv('GEMINI_API_KEY')


# Initialize the Gemini Pro API
genai.configure(api_key=gemini_key)

handler = WebhookHandler(secret)
configuration = Configuration(
    access_token=token
)


def linebot(request):
    body = request.get_data(as_text=True)
    json_data = json.loads(body)
    try:

        signature = request.headers['X-Line-Signature']
        handler.handle(body, signature)
        event = json_data['events'][0]
        reply_token = event['replyToken']
        user_id = event['source']['userId']
        msg_type = event['message']['type']

        fdb = firebase.FirebaseApplication(firebase_url, None)
        user_chat_path = f'chat/{user_id}'
        chat_state_path = f'state/{user_id}'
        chatgpt = fdb.get(user_chat_path, None)

        if msg_type == 'text':
            msg = event['message']['text']

            if chatgpt is None:
                messages = []
            else:
                messages = chatgpt
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.show_loading_animation(ShowLoadingAnimationRequest(
                    chatId=user_id, loadingSeconds=20))

                if msg == '!清空':
                    reply_msg = '已清空'
                    fdb.delete(user_chat_path, None)
                elif msg == '紅外線圖':
                    url = "https://www.cwa.gov.tw/Data/satellite/LCC_IR1_CR_2750/LCC_IR1_CR_2750-2024-04-26-00-00.jpg"
                    response = requests.get(url)
                    if response.status_code == 200:
                        image_data = response.content
                        image = Image.open(BytesIO(image_data))

                        model = genai.GenerativeModel('gemini-pro-vision')
                        response = model.generate_content([
                            "Does following image looks moist? Reply Yes or No in traditional chinese",
                            image
                        ])
                        print(response.text)
                        reply_msg = f"地板是否是濕的：{response.text}"
                else:
                    model = genai.GenerativeModel('gemini-pro')
                    messages.append({'role': 'user', 'parts': [msg]})
                    response = model.generate_content(messages)
                    messages.append(
                        {'role': 'model', 'parts': [response.text]})
                    reply_msg = response.text
                    # 更新firebase中的對話紀錄
                    fdb.put_async(user_chat_path, None, messages)

                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[
                            TextMessage(text=reply_msg),
                        ]))
        else:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[
                            TextMessage(text='你傳的不是文字訊息呦'),
                        ]))

    except Exception as e:
        detail = e.args[0]
        print(detail)
    return 'OK'
