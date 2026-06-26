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

`sts2-mod-uploader` 官方 release 同时提供 `linux-x64` 包。这个 reusable workflow 默认在 `ubuntu-latest` 下载 `ModUploader-linux-x64.zip`，准备 uploader workspace，然后执行 `ModUploader upload -w <workspace>`。

注意：uploader 使用 Steamworks API 初始化 Steam。GitHub-hosted runner 是否能完成 Steam 登录态取决于 Steam 环境；如果 `SteamAPI.InitEx` 失败，就需要改用能登录 Steam 的 self-hosted runner。

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
      dry_run: true
```

默认约定：

- uploader 下载地址：`https://github.com/megacrit/sts2-mod-uploader/releases/download/<version>/ModUploader-linux-x64.zip`
- workspace 路径：`.github/workshop/<VersionInfo.Name>`
- 发布内容来源：`<MOD目录>/modPublish`
- Workshop item ID：默认读取 workspace 下的 `mod_id.txt`
- change note：优先从 `CHANGELOG.md` 中匹配当前版本，找不到时使用 `Release v<version>`

每个子 MOD 仓库需要提交一个 workspace，例如：

```text
.github/workshop/BetterSaveSlots/
  content/
  image.png
  mod_id.txt
  workshop.json
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

可选参数：

```yaml
jobs:
  publish-workshop:
    needs: release
    uses: JMC2002/STS2_Mods_Actions/.github/workflows/publish-workshop.yml@main
    with:
      runs_on: '["ubuntu-latest"]'
      uploader_version: v0.1.0
      uploader_platform: linux-x64
      uploader_archive_path: tools/ModUploader-linux-x64.zip
      workshop_workspace: .github/workshop/BetterSaveSlots
      workshop_id: '3747533700'
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
