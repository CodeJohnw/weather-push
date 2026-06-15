import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests


DEFAULT_QWEATHER_API_HOST = "pp5u9xmvay.re.qweatherapi.com"
DEFAULT_LOCATION = "117.00,39.14"
DEFAULT_CITY_NAME = "天津市西青区杨柳青镇"
DEFAULT_AUDIO_FILE = "output/weather.mp3"
DEFAULT_PUSH_FILE = "output/push.json"
DEFAULT_REPO_AUDIO_URL = "https://raw.githubusercontent.com/CodeJohnw/weather-push/main/output/weather.mp3"
SERVER_CHAN_URL = "https://sctapi.ftqq.com/{sendkey}.send"
OPENAI_SPEECH_URL = "https://api.openai.com/v1/audio/speech"


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing environment variable: {name}. "
            f"Please add it in GitHub Settings -> Secrets and variables -> Actions."
        )
    return value


def fetch_weather(api_key: str, location: str, api_host: str) -> dict[str, Any]:
    weather_url = f"https://{api_host}/v7/weather/3d"
    response = requests.get(
        weather_url,
        params={"location": location, "key": api_key},
        timeout=15,
    )

    if not response.ok:
        raise RuntimeError(
            "QWeather HTTP request failed. "
            f"status={response.status_code}, url={response.url}, body={response.text}"
        )

    data = response.json()

    if data.get("code") != "200":
        raise RuntimeError(
            "QWeather API failed. "
            f"code={data.get('code')}, location={location}, host={api_host}, response={data}"
        )

    daily = data.get("daily")
    if not daily:
        raise RuntimeError(f"QWeather API returned no daily forecast: {data}")

    return daily[0]


def build_weather_text(today: dict[str, Any], city_name: str) -> tuple[str, str]:
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


def synthesize_speech(text: str, output_file: str) -> None:
    openai_api_key = require_env("OPENAI_API_KEY")
    model = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
    voice = os.getenv("OPENAI_TTS_VOICE", "coral")
    instructions = os.getenv(
        "OPENAI_TTS_INSTRUCTIONS",
        "用温柔、自然、像家人早晨问候的中文语气朗读，语速稍慢，清晰亲切。",
    )

    response = requests.post(
        OPENAI_SPEECH_URL,
        headers={
            "Authorization": f"Bearer {openai_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "voice": voice,
            "input": text,
            "instructions": instructions,
            "response_format": "mp3",
        },
        timeout=60,
    )

    if not response.ok:
        raise RuntimeError(
            "OpenAI speech request failed. "
            f"status={response.status_code}, body={response.text}"
        )

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(response.content)


def build_audio_url() -> str:
    repo_audio_url = os.getenv("REPO_AUDIO_URL", DEFAULT_REPO_AUDIO_URL)
    cache_key = os.getenv("GITHUB_RUN_ID") or os.getenv("AUDIO_CACHE_KEY")
    return f"{repo_audio_url}?ts={cache_key}" if cache_key else repo_audio_url


def prepare_push_payload() -> dict[str, str]:
    location = os.getenv("LOCATION", DEFAULT_LOCATION)
    city_name = os.getenv("CITY_NAME", DEFAULT_CITY_NAME)
    qweather_api_host = os.getenv("QWEATHER_API_HOST", DEFAULT_QWEATHER_API_HOST)
    qweather_key = require_env("QWEATHER_KEY")

    today = fetch_weather(qweather_key, location, qweather_api_host)
    title, weather_text = build_weather_text(today, city_name)

    if os.getenv("PUSH_MODE", "voice") == "voice":
        audio_file = os.getenv("AUDIO_FILE", DEFAULT_AUDIO_FILE)
        audio_url = build_audio_url()
        synthesize_speech(weather_text, audio_file)
        title = f"{city_name}语音天气"
        desp = f"""妈，早上好。今天的天气语音在这里：

[点击播放语音天气]({audio_url})

文字版：

{weather_text}
"""
    else:
        desp = weather_text

    return {"title": title, "desp": desp}


def write_push_payload(payload: dict[str, str], output_file: str) -> None:
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_push_payload(input_file: str) -> dict[str, str]:
    return json.loads(Path(input_file).read_text(encoding="utf-8"))


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
    parser.add_argument("--prepare-only", action="store_true", help="Generate push payload and audio, then exit.")
    parser.add_argument("--send-prepared", help="Send a previously generated push payload JSON file.")
    args = parser.parse_args()

    if args.send_prepared:
        payload = read_push_payload(args.send_prepared)
        sendkey = require_env("SENDKEY")
        result = send_to_wechat(sendkey, payload["title"], payload["desp"])
        print(f"Push succeeded: {result}")
        return 0

    payload = prepare_push_payload()

    if args.dry_run:
        print(payload["title"])
        print()
        print(payload["desp"])
        return 0

    if args.prepare_only:
        output_file = os.getenv("PUSH_FILE", DEFAULT_PUSH_FILE)
        write_push_payload(payload, output_file)
        print(f"Prepared push payload: {output_file}")
        return 0

    sendkey = require_env("SENDKEY")
    result = send_to_wechat(sendkey, payload["title"], payload["desp"])
    print(f"Push succeeded: {result}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
