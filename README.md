# STS2 Mods Actions

个人使用的杀戮尖塔2mod仓库的公用actions。

这个仓库集中维护 STS2 子 MOD 复用的 GitHub Actions。建议保持 public，这样各个 public 子 MOD 可以直接通过 reusable workflow 调用。

## Release wrapper

在子 MOD 仓库中创建 `.github/workflows/release.yml`：

```yaml
name: Release Mod

on:
  push:
    tags:
      - 'v*'

permissions:
  contents: write

jobs:
  release:
    uses: JMC2002/STS2_Mods_Actions/.github/workflows/release-mod.yml@main
```

可选参数：

```yaml
jobs:
  release:
    uses: JMC2002/STS2_Mods_Actions/.github/workflows/release-mod.yml@main
    with:
      version_info_path: ./MyMod/VersionInfo.cs
      mod_path: ./MyMod
      docs: README.md README_en.md CHANGELOG.md LICENSE.txt LICENSE
```

默认行为会自动寻找 `VersionInfo.cs`，读取其中的 `Name` 和 `Version`，再按 MOD 名称寻找发布目录并打包 `modPublish`。

## Code lines wrapper

在子 MOD 仓库中创建 `.github/workflows/code-lines.yml`：

```yaml
name: Code Stats Badges

on:
  push:
    branches:
      - main
      - master
  workflow_dispatch:

permissions:
  contents: write

jobs:
  update-code-stats-badges:
    uses: JMC2002/STS2_Mods_Actions/.github/workflows/code-lines.yml@main
```

可选参数：

```yaml
jobs:
  update-code-stats-badges:
    uses: JMC2002/STS2_Mods_Actions/.github/workflows/code-lines.yml@main
    with:
      workflow_url: https://github.com/${{ github.repository }}/actions/workflows/code-lines.yml
```

默认会统计常见代码文件，生成 `.github/badges/code-lines*.svg`，并更新 `README.md` / `README_en.md` 中的徽章块。README 文件不存在时会跳过对应更新。

## Steam Workshop wrapper

这个 reusable workflow 默认从 `JMC2002/sts2-mod-uploader@main` 构建增强版 `ModUploader`，准备 uploader workspace，然后执行 `ModUploader upload -w <workspace>`。

注意：uploader 使用 Steamworks API 初始化 Steam。推荐使用已登录 Steam 客户端的 Windows self-hosted runner；GitHub-hosted runner 通常没有 Steam 登录态，`SteamAPI.InitEx` 很可能失败。

在子 MOD 的 release wrapper 中追加一个发布 Workshop 的 job：

```yaml
name: Release Mod

on:
  push:
    tags:
      - 'v*'

permissions:
  contents: write

jobs:
  release:
    uses: JMC2002/STS2_Mods_Actions/.github/workflows/release-mod.yml@main

  publish-workshop:
    needs: release
    uses: JMC2002/STS2_Mods_Actions/.github/workflows/publish-workshop.yml@main
    with:
      runs_on: '["self-hosted", "Windows", "X64", "steam", "workshop"]'
      uploader_platform: win-x64
      dry_run: true
```

默认约定：

- uploader 来源：默认 checkout 并构建 `JMC2002/sts2-mod-uploader@main`
- workspace 路径：`<MOD目录>/workshop`；旧的 `.github/workshop/<VersionInfo.Name>` 仍会 fallback 兼容，但新 MOD 建议使用前者
- 发布内容来源：`<MOD目录>/modPublish`
- Workshop item ID：默认读取 workspace 下的 `mod_id.txt`
- change note：SteamUGC API 只接受单条改动说明，不能像描述一样按语言本地化；默认 `change_note_language: combined`，把 `CHANGELOG.md` / `CHANGELOG_en.md` 中当前版本的中英内容合并成一条，并带上 changelog header 中的版本号和日期。也可以显式设为 `chinese`、`english` 或 `auto`
- Workshop 描述：自动读取 workspace 下的 `workshop_zh.txt` / `workshop_en.txt` Markdown，转换为 Steam BBCode 后由增强版 uploader 提交；中文描述会同时用于 `schinese` 和 `tchinese`，缺少某个语言会直接跳过，并在日志摘要里列出实际应用的语言

每个子 MOD 仓库需要提交一个 workspace，例如：

```text
BetterSaveSlots/workshop/
  image.png
  mod_id.txt
  workshop.json
  workshop_zh.txt
  workshop_en.txt
```

如果想把 uploader zip 固定在这个 Actions 仓库里，也可以把 zip 放到例如 `tools/ModUploader-linux-x64.zip`，然后在 wrapper 中指定：

```yaml
jobs:
  publish-workshop:
    needs: release
    uses: JMC2002/STS2_Mods_Actions/.github/workflows/publish-workshop.yml@main
    with:
      uploader_archive_path: tools/ModUploader-linux-x64.zip
      dry_run: false
```

这会额外 checkout `JMC2002/STS2_Mods_Actions@main` 来读取 zip。若 zip 放在调用方 MOD 仓库中，将 `uploader_archive_repository` 设为空字符串即可。

正式启用前建议先用 `dry_run: true` 跑一次，确认 workspace 的 `content` 和 `workshop.json` 更新正确后再改为 `false`。

正式上传时，wrapper 会把 uploader 输出同时写到 self-hosted runner 的 `$RUNNER_WORKSPACE/_steam-workshop-logs/<run-id>-<attempt>-workshop-upload.log`，并上传同名 Actions artifact，方便排查 Steamworks 返回的模糊错误。

可选参数：

```yaml
jobs:
  publish-workshop:
    needs: release
    uses: JMC2002/STS2_Mods_Actions/.github/workflows/publish-workshop.yml@main
    with:
      runs_on: '["ubuntu-latest"]'
      uploader_version: v0.2.0
      uploader_repository: JMC2002/sts2-mod-uploader
      uploader_platform: linux-x64
      build_uploader_from_source: false
      uploader_archive_path: tools/ModUploader-linux-x64.zip
      workshop_workspace: BetterSaveSlots/workshop
      workshop_id: '3747533700'
      changelog_path: CHANGELOG.md
      changelog_en_path: CHANGELOG_en.md
      change_note_language: combined
      workshop_description_zh_path: workshop_zh.txt
      workshop_description_en_path: workshop_en.txt
      convert_markdown_to_bbcode: true
      dry_run: false
```

## Quark Drive wrapper

在子 MOD 仓库根目录提交 `quark.json`：

```json
{
  "folderId": "夸克MOD发布文件夹ID",
  "historyFolderId": "历史版本文件夹ID",
  "historyFolderName": "历史版本"
}
```

`folderId` / `historyFolderId` 不是登录凭证，可以放仓库里；夸克登录态必须放 GitHub Actions Secret：

```powershell
gh secret set QUARK_COOKIE --repo JMC2002/SlayTheSpire2_QuickSL
```

在子 MOD 的 release wrapper 中追加一个发布夸克网盘的 job：

```yaml
name: Release Mod

on:
  push:
    tags:
      - 'v*'

permissions:
  contents: write

jobs:
  release:
    uses: JMC2002/STS2_Mods_Actions/.github/workflows/release-mod.yml@main

  publish-quark:
    needs: release
    uses: JMC2002/STS2_Mods_Actions/.github/workflows/publish-quark.yml@main
    secrets:
      quark_cookie: ${{ secrets.QUARK_COOKIE }}
```

默认行为：

- 自动寻找 `VersionInfo.cs`，读取 `Name` 和 `Version`
- 按 MOD 名称寻找发布目录
- 按 GitHub Release 同样规则打包 `<Name>_<Version>.zip`
- 读取仓库根目录 `quark.json`
- 将夸克目标文件夹中的现有 `.zip` 移动到 `historyFolderId`
- 上传新 zip 到 `folderId`
- 上传后再次列目录校验文件存在

这个 workflow 当前内部使用 Rust 版 `quarkpan` CLI 上传文件，并缓存 CLI 二进制以减少后续运行时间；子仓库只需要调用这个 reusable workflow，不需要关心内部上传实现。正式启用前可以先 dry run：

```yaml
jobs:
  publish-quark:
    needs: release
    uses: JMC2002/STS2_Mods_Actions/.github/workflows/publish-quark.yml@main
    with:
      dry_run: true
    secrets:
      quark_cookie: ${{ secrets.QUARK_COOKIE }}
```

可选参数：

```yaml
jobs:
  publish-quark:
    needs: release
    uses: JMC2002/STS2_Mods_Actions/.github/workflows/publish-quark.yml@main
    with:
      version_info_path: ./Core/VersionInfo.cs
      mod_path: ./QuickSL
      quark_config_path: quark.json
      move_existing_zip: true
      dry_run: false
    secrets:
      quark_cookie: ${{ secrets.QUARK_COOKIE }}
```
