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
