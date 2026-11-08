# Homebrew formula for the thin HangarLLM `lite` CLI (hangarllm[cli]).
#
# Ships in the BerriAI/homebrew-hangarllm tap, not homebrew-core: it builds the
# published hangarllm sdist with the `cli` extra into a dedicated virtualenv and
# pulls the extra's deps from PyPI. That is the low-maintenance path for a
# fast-moving Python CLI; the resource-stanza alternative would need every
# transitive dep re-pinned with a fresh sha256 on each release.
#
# RELEASE STEP (see README.md in this directory): point `url` + `sha256` at the
# PyPI sdist of the first hangarllm version that ships the `cli` extra. `version`
# is parsed from `url`, and the build installs exactly that version, so the three
# stay in lockstep automatically.
class Lite < Formula
  include Language::Python::Virtualenv

  desc "Thin client for the HangarLLM proxy: lite login, lite claude/codex/opencode"
  homepage "https://github.com/valteresj2/HangarLLM#readme"
  url "https://files.pythonhosted.org/packages/source/l/hangarllm/hangarllm-REPLACE_AT_RELEASE.tar.gz"
  sha256 "REPLACE_AT_RELEASE"
  license "MIT"

  depends_on "python@3.13"

  def install
    virtualenv_create(libexec, "python3.13")
    system libexec/"bin/pip", "install", "#{buildpath}[cli]"
    bin.install_symlink libexec/"bin/lite"
  end

  test do
    assert_match "login", shell_output("#{bin}/lite --help")
  end
end
