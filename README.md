# Daily Weather Push

每天通过 GitHub Actions 拉取和风天气，并用 Server酱 Turbo 推送到微信。

## 需要准备

1. Server酱 Turbo 的 SendKey。
2. 和风天气的 API Key。
3. 一个 GitHub 仓库。

注意：SendKey 属于密钥，不要写进代码。你已经在聊天里贴过一次，建议去 Server酱里更换一个新的 SendKey。

## GitHub Secrets

进入仓库：

`Settings -> Secrets and variables -> Actions -> New repository secret`

添加：

```text
SENDKEY=你的Server酱SendKey
QWEATHER_KEY=你的和风天气Key
```

## 城市配置

默认城市是合肥：

```text
LOCATION=101220101
CITY_NAME=合肥
```

默认和风天气 API Host 是：

```text
QWEATHER_API_HOST=pp5u9xmvay.re.qweatherapi.com
```

如果要换城市，可以在 GitHub 仓库的：

`Settings -> Secrets and variables -> Actions -> Variables`

添加仓库变量：

```text
LOCATION=城市ID
CITY_NAME=城市名
```

如果和风天气控制台里你的项目显示了不同的 API Host，也在这里添加：

```text
QWEATHER_API_HOST=你的API Host
```

## 本地测试

只预览内容，不推送：

```bash
export QWEATHER_KEY=你的和风天气Key
python weather.py --dry-run
```

真实推送：

```bash
export QWEATHER_KEY=你的和风天气Key
export SENDKEY=你的Server酱SendKey
python weather.py
```

## 定时说明

`.github/workflows/weather.yml` 里的：

```yaml
cron: "0 23 * * *"
```

表示 UTC 23:00，也就是北京时间/新加坡时间每天 07:00 左右运行。GitHub Actions 的定时任务可能会有几分钟延迟。
