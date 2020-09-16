#!/usr/bin/env python3.7

import functools
import sys
import time
import traceback

import requests
import zulip

GOTIFY_POST_URL = sys.argv[1]
ZULIPRC_PATH = "zuliprc"
IGNORED_SENDER = None


def time_based_func_cache(seconds):
    def wrap(func):
        cache = {}

        def wrapper(*args, **kwargs):
            k = (args, tuple(kwargs.items()))
            if k in cache and cache[k][0] >= (
                time.monotonic() - seconds
            ):  # cache is good
                pass
            else:
                cache[k] = (time.monotonic(), func(*args, **kwargs))
            return cache[k][1]

        return wrapper

    return wrap


@time_based_func_cache(2 * 60)
def send_gotify_message(title, message):
    with requests.Session() as sess:
        sess.post(GOTIFY_POST_URL, params={"title": title, "message": message})


def get_event_sender_email(event):
    if event["type"] == "message":
        sender = event["message"]["sender_email"]
    elif event["type"] == "typing":
        sender = event["sender"]["email"]
    elif event["type"] == "presence":
        sender = event["email"]
    elif event["type"] == "update_message":
        sender = event["sender"]
    else:
        sender = "UNSUPPORTED EVENT TYPE"

    return sender


def handle_event_core(event, *, client):
    print(event["type"], event)

    sender = get_event_sender_email(event)

    if sender == (IGNORED_SENDER or client.email):
        return

    title, message = None, None
    if event["type"] == "message":
        message = event["message"]["content"]
        if event["message"]["type"] == "stream":
            title = "{sender_full_name} sent a message to #{display_recipient} > {subject}".format(
                **event["message"]
            )
        elif event["message"]["type"] == "private":
            title = "{sender_full_name} sent a private message".format(
                **event["message"]
            )
        else:
            print(f"Unknown message type: {event['message']['type']}")
    elif event["type"] == "typing":
        if event["op"] == "start":
            title = "Typing..."
            message = f"{sender} started typing"
    elif event["type"] == "presence":
        presence = list(event["presence"].values())[0]  # TODO
        title = f"User is {presence['status']}"
        message = f"{sender} is {presence['status']} on {presence['client']}"
    elif event["type"] in ["heartbeat", "update_message_flags"]:
        pass
    else:
        title, message = f"{event['type']}", str(event)

    if title is not None and message is not None:
        send_gotify_message(title, message)


def handle_event(*args, **kwargs):
    try:
        handle_event_core(*args, **kwargs)
    except Exception as e:
        print()
        print()
        traceback.print_exc()
        print(args, kwargs)
        print()
        print()


def main(*, zuliprc_path):
    client = zulip.Client(config_file=zuliprc_path)
    client.call_on_each_event(functools.partial(handle_event, client=client))


if __name__ == "__main__":
    main(zuliprc_path=ZULIPRC_PATH)
