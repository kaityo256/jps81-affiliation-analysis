# 作業ルール

## Git・GitHub CLIの実行

- すべての `git` および `gh` コマンドは、読み取り専用の操作を含め、サンドボックス内では実行しない。
- `git` および `gh` コマンドはユーザーの承認のもと、サンドボックス外でユーザー権限により実行する。実行時は `sandbox_permissions: "require_escalated"` を指定し、`justification` に実行目的を明記して承認を求める。
- 使用するGitHubアカウントは `kaityo256`。

## 実装言語・Python環境

- 実装はPythonで行う。ただし、`PLAN.md` で定めた `wget` による取得の実行には、シェルスクリプトまたはGNU Makefileを使用する。
- 必要なPython環境は `uv` で仮想環境を作成し、その仮想環境内でライブラリの導入とPythonコードの実行を行う。
- すべての `uv` コマンドはサンドボックス内では実行せず、ユーザーの承認のもと、サンドボックス外でユーザー権限により実行する。実行時は `sandbox_permissions: "require_escalated"` を指定し、`justification` に実行目的を明記して承認を求める。
- ライブラリのインストールは `uv` を使用し、ユーザーの承認を得て行う。
