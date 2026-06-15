import argparse
import os
import sys
from typing import Any

import requests


QWEATHER_URL = "https://devapi.qweather.com/v7/weather/3d"
SERVER_CHAN_URL = "https://sctapi.ftqq.com/{sendkey}.send"


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing environment variable: {name}. "
            f"Please add it in GitHub Settings -> Secrets and variables -> Actions."
        )
    return value


def fetch_weather(api_key: str, location: str) -> dict[str, Any]:
    response = requests.get(
        QWEATHER_URL,
        params={"location": location, "key": api_key},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("code") != "200":
        raise RuntimeError(
            "QWeather API failed. "
            f"code={data.get('code')}, location={location}, response={data}"
        )

    daily = data.get("daily")
    if not daily:
        raise RuntimeError(f"QWeather API returned no daily forecast: {data}")

    return daily[0]


def build_message(today: dict[str, Any], city_name: str) -> tuple[str, str]:
    text_day = today.get("textDay", "天气未知")
    temp_min = today.get("tempMin", "?")
    temp_max = today.get("tempMax", "?")
    wind = today.get("windDirDay", "风向未知")
    precip = today.get("precip", "0.0") or "0.0"
    humidity = today.get("humidity", "?")

    try:
        precip_value = float(precip)
    except ValueError:
        precip_value = 0.0

    umbrella_tip = "有降水可能，出门记得带伞。" if precip_value > 0 else "看起来不太会下雨，出门也可以轻装一点。"

    title = f"{city_name}早安天气"
    desp = f"""妈，早上好。

今天{city_name}{text_day}，{temp_min}~{temp_max}℃。
{umbrella_tip}
白天{wind}，湿度约{humidity}%。

注意增减衣服，路上慢一点。
"""
    return title, desp


def send_to_wechat(sendkey: str, title: str, desp: str) -> dict[str, Any]:
    response = requests.post(
        SERVER_CHAN_URL.format(sendkey=sendkey),
        data={"title": title, "desp": desp},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("code") not in (0, "0"):
        raise RuntimeError(f"ServerChan API failed. response={data}")

    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Push daily weather to WeChat via ServerChan Turbo.")
    parser.add_argument("--dry-run", action="store_true", help="Print the message without sending it.")
    args = parser.parse_args()

    location = os.getenv("LOCATION", "101220101")
    city_name = os.getenv("CITY_NAME", "合肥")
    qweather_key = require_env("QWEATHER_KEY")

    today = fetch_weather(qweather_key, location)
    title, desp = build_message(today, city_name)

    if args.dry_run:
        print(title)
        print()
        print(desp)
        return 0

    sendkey = require_env("SENDKEY")
    result = send_to_wechat(sendkey, title, desp)
    print(f"Push succeeded: {result}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
