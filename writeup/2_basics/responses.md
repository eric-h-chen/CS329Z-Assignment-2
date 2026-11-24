# Section 2: Basics

## 2.2.1 Docker ensures reproducibility

**Problem 1 (`docker-setup`)**

1. Paste the commands you used to pull `ubuntu:22.04` and start an interactive container, followed by the output from inside the container that confirms its operating system (e.g., `cat /etc/os-release`).

   ```text
   $ docker pull ubuntu:22.04
   22.04: Pulling from library/ubuntu
   Digest: sha256:f64b2ffc2f10ab8f8505aa56b2664bd846cbb9df87c7e2532e30f7667021c0e6
   Status: Image is up to date for ubuntu:22.04
   docker.io/library/ubuntu:22.04

   $ docker run -i --rm ubuntu:22.04 bash
   cat /etc/os-release
   PRETTY_NAME="Ubuntu 22.04.5 LTS"
   NAME="Ubuntu"
   VERSION_ID="22.04"
   VERSION="22.04.5 LTS (Jammy Jellyfish)"
   VERSION_CODENAME=jammy
   ID=ubuntu
   ID_LIKE=debian
   HOME_URL="https://www.ubuntu.com/"
   SUPPORT_URL="https://help.ubuntu.com/"
   BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"
   PRIVACY_POLICY_URL="https://www.ubuntu.com/legal/terms-and-policies/privacy-policy"
   UBUNTU_CODENAME=jammy
   exit
   ```

## 2.2.2 Harbor defines evaluation primitives

**Problem 2 (`harbor-setup`)**

1. Paste the output of `uv run harbor --version` and `docker version`.

   ```text
   $ uv run harbor --version
   0.18.0

   $ docker version
   Client:
    Version:           29.8.2
    API version:       1.56
    Go version:        go1.26.8
    Git commit:        7fc2dff
    Built:             Sun Oct 11 12:42:20 2026
    OS/Arch:           darwin/arm64
    Context:           orbstack

   Server: Docker Engine - Community
    Engine:
     Version:          29.8.2
     API version:      1.56 (minimum version 1.40)
     Go version:       go1.26.8
     Git commit:       8af9fe3
     Built:            Wed Sep 30 19:32:49 2026
     OS/Arch:          linux/arm64
     Experimental:     true
    containerd:
     Version:          v2.3.6
     GitCommit:        ee2735368117d2eb259779949d5e75cdafec9761
    runc:
     Version:          1.5.2
     GitCommit:        29dd3dc2b13b4123162e5fe132504bb4b15569f1
    docker-init:
     Version:          0.19.0
     GitCommit:        de40ad0
   ```

2. From `uv run harbor --help`, which commands start an evaluation job and browse completed results?

   `harbor run` starts an evaluation job (it is an alias for `harbor job start`; `harbor job resume` continues an interrupted one). `harbor view` starts a local web server for browsing completed jobs, including trial trajectories, verifier logs, and rewards. The `Server` section of `docker version` above confirms the Docker client can reach the Docker daemon.
