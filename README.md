# wordpress-plugin-updates

自作のWordPressプラグインの配布物を置くリポジトリです。wordpress.orgのプラグインディレクトリに載せていないプラグインが、
ここに置いた更新情報を見て、管理画面のプラグイン一覧に更新の通知を出します。

- `<slug>/info.json` — 最新版の情報（版、対応するWordPressとPHPの版、zipのURL、説明、変更履歴）
- `<slug>/<slug>-<版>.zip` — 配布物。版ごとに置き、上書きしません
- `.github/workflows/release.yml` — 各プラグインのリポジトリから呼ぶ共通のworkflow。タグのpushでzipと`info.json`を作り、ここへコミットします
- `scripts/make_info.py` — プラグインのヘッダーと`readme.txt`から`info.json`を作ります

`<slug>/`以下は共通のworkflowが書き込みます。手で編集しないでください。

プラグインのソースは、それぞれ別のリポジトリにあります。プラグインのライセンスはGPLv2 or laterです。

## テスト

```bash
python3 -m unittest discover -s tests -v
```
