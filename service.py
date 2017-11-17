import json
import urllib.parse
import boto3
import math
import dateutil.parser
import datetime
import time
import os
import logging
import pickle
import string
import operator

s3 = boto3.resource('s3')
s3_client = boto3.client('s3')
s3_client.download_file('mercbucket', 'words_to_articles.pickle', '/tmp/words_to_article.pickle')
s3_client.download_file('mercbucket', 'knowledge_base.pickle', '/tmp/knowledge_base.pickle')
with open('/tmp/words_to_article.pickle', 'rb') as handle:
    words_to_articles = pickle.load(handle)
with open('/tmp/knowledge_base.pickle', 'rb') as handle:
    knowledge_base = pickle.load(handle)
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

""" --- Helpers to build responses which match the structure of the necessary dialog actions --- """


def get_slots(intent_request):
    return intent_request['currentIntent']['slots']


def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit,
            'message': message
        }
    }

def elicit_intent(session_attributes, intent_name, slots, slot_to_elicit, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitIntent',
            'message': message
        }
    }



def close(session_attributes, fulfillment_state, message):
    response = {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState': fulfillment_state,
            'message': message
        }
    }

    return response


def delegate(session_attributes, slots):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Delegate',
            'slots': slots
        }
    }

def addSessionAttribute(session_attributes, key, value):
    return{
        session_attributes

    }



""" --- Helper Functions --- """


def parse_int(n):
    try:
        return int(n)
    except ValueError:
        return float('nan')


def build_validation_result(is_valid, violated_slot, message_content):
    if message_content is None:
        return {
            "isValid": is_valid,
            "violatedSlot": violated_slot,
        }

    return {
        'isValid': is_valid,
        'violatedSlot': violated_slot,
        'message': {'contentType': 'PlainText', 'content': message_content}
    }


def isvalid_date(date):
    try:
        dateutil.parser.parse(date)
        return True
    except ValueError:
        return False

def get_news(query):
    for word in query.split():
        contained = words_to_articles[word]

    print(word + " is located in: ")
    for k in contained:
        print(k)

    for k in contained:
        highestscore = 0
    score = knowledge_base[k][2][word]
    print("Importance score is: " + str(score) + " in article" + k)
    if k not in possible_target_article:
        possible_target_article[k] = score
    else:
        possible_target_article[k] += score
    print("")

    target_article = max(possible_target_article.items(), key=operator.itemgetter(1))[0]
    print(target_article + " has the highest importance score with " + str(possible_target_article[target_article]))
    print("")

    print("Title: " + knowledge_base[target_article][0])
    print("URL: " + knowledge_base[target_article][1])
    summary = knowledge_base[target_article][3]
    print("Summary: ")
    for listitem in summary:
        print(listitem)




def validate_order_flowers(flower_type, date, pickup_time):
    flower_types = ['lilies', 'roses', 'tulips']
    if flower_type is not None and flower_type.lower() not in flower_types:
        return build_validation_result(False,
                                       'FlowerType',
                                       'We do not have {}, would you like a different type of flower?  '
                                       'Our most popular flowers are roses'.format(flower_type))

    if date is not None:
        if not isvalid_date(date):
            return build_validation_result(False, 'PickupDate',
                                           'I did not understand that, what date would you like to pick the flowers up?')
        elif datetime.datetime.strptime(date, '%Y-%m-%d').date() <= datetime.date.today():
            return build_validation_result(False, 'PickupDate',
                                           'You can pick up the flowers from tomorrow onwards.  What day would you like to pick them up?')

    if pickup_time is not None:
        if len(pickup_time) != 5:
            # Not a valid time; use a prompt defined on the build-time model.
            return build_validation_result(False, 'PickupTime', None)

        hour, minute = pickup_time.split(':')
        hour = parse_int(hour)
        minute = parse_int(minute)
        if math.isnan(hour) or math.isnan(minute):
            # Not a valid time; use a prompt defined on the build-time model.
            return build_validation_result(False, 'PickupTime', None)

        if hour < 10 or hour > 16:
            # Outside of business hours
            return build_validation_result(False, 'PickupTime',
                                           'Our business hours are from ten a m. to five p m. Can you specify a time during this range?')

    return build_validation_result(True, None, None)


""" --- Functions that control the bot's behavior --- """

""" Get the users name and store it in Session Data"""

def GetUsersName(intent_request):
    source = intent_request['invocationSource']
    usersName = get_slots(intent_request)["usersName"]
    slots = get_slots(intent_request)
    sessionAttributes = intent_request['sessionAttributes']


    if usersName == None and "firstMessage" not in sessionAttributes:
        sessionAttributes["firstMessage"] = "false"
        return delegate(intent_request['sessionAttributes'], slots)


    if usersName == None and "firstMessage" in sessionAttributes:
        message = "Buddy..Come on. I'm a bot. Give me an easy name. Like Dave, or Karen." \
                  " I can't recognize yours"
        return elicit_slot(intent_request['sessionAttributes'],
                           intent_request['currentIntent']['name'],
                           slots,
                           'usersName',
                           {'contentType': 'PlainText', 'content': message}
                           )
    #Later, we can check our S3 db and see if the user is new or not and change the message.
    message = "Hello " + usersName + "! What would you like me to tell you about today?"
    userQuerySlots = {
        "usersQuery": "null"
    }
    sessionAttributes["usersName"] = usersName  # Store username in session data
    return elicit_slot(sessionAttributes,
                       "GetUsersQuery",
                       userQuerySlots,
                       "usersQuery",
                       {'contentType': 'PlainText', 'content': message}
                       )

def GetUsersQuery(intent_request):
    source = intent_request['invocationSource']
    sessionAttributes = intent_request['sessionAttributes']

    #User needs to introduce themselves first if no name known
    if "usersName" not in sessionAttributes:
        message = "Ay girl. Before I start helping you out, why don't we start with your name?"
        return elicit_slot(sessionAttributes,
                           "GetUsersName",
                           {"usersName": "null"},
                           "usersName",
                           {'contentType': 'PlainText', 'content': message}
                           )

        return delegate(sessionAttributes, slots)

    #Need news logic here.


""" --- Intents --- """


def dispatch(intent_request):
    """
    Called when the user specifies an intent for this bot.
    """

    logger.debug(
        'dispatch userId={}, intentName={}'.format(intent_request['userId'], intent_request['currentIntent']['name']))

    intent_name = intent_request['currentIntent']['name']

    # Dispatch to your bot's intent handlers
    if intent_name == 'GetUsersName':
        return GetUsersName(intent_request)
    if intent_name == 'GetUsersQuery':
        return GetUsersQuery(intent_request)

    raise Exception('Intent with name ' + intent_name + ' not supported')


""" --- Main handler --- """


def handler(event, context):
    return dispatch(event)


