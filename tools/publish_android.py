"""Publish a signed APK, then atomically expose its update manifest."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid

from dotenv import dotenv_values
import paramiko


def run():
    root = Path(__file__).resolve().parents[1]
    client = root.parent / "edu_helper_client"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apk",
        type=Path,
        default=client / "build/app/outputs/flutter-apk/app-release.apk",
    )
    parser.add_argument("--notes", required=True)
    parser.add_argument(
        "--java",
        default=os.environ.get("JAVA_HOME", "")
        and str(Path(os.environ["JAVA_HOME"]) / "bin/java.exe")
        or shutil.which("java"),
    )
    parser.add_argument("--sdk", type=Path)
    args = parser.parse_args()
    if len(args.notes) > 4000:
        parser.error("Release notes must be at most 4000 characters")
    sdk = args.sdk
    if sdk is None:
        properties = (client / "android/local.properties").read_text()
        sdk = Path(
            re.search(r"^sdk.dir=(.+)$", properties, re.M)[1]
            .replace("\\\\", "\\")
            .strip()
        )
    versions = [
        p
        for p in (sdk / "build-tools").iterdir()
        if re.fullmatch(r"\d+\.\d+\.\d+", p.name)
    ]
    tools = max(versions, key=lambda p: tuple(map(int, p.name.split("."))))
    apk = args.apk.resolve(strict=True)
    # Refuse unsigned APKs before any remote publication.
    verification = subprocess.run(
        [
            args.java,
            "-jar",
            str(tools / "lib/apksigner.jar"),
            "verify",
            "--print-certs",
            str(apk),
        ],
        check=True,
        capture_output=True,
        encoding="utf-8",
    ).stdout
    signer = re.search(
        r"Signer #1 certificate SHA-256 digest: ([a-fA-F0-9]{64})", verification
    )
    if not signer:
        raise RuntimeError("Cannot read APK signing certificate")
    signer_hash = signer[1].lower()
    aapt = tools / ("aapt.exe" if os.name == "nt" else "aapt")
    badging = subprocess.run(
        [str(aapt), "dump", "badging", str(apk)],
        check=True,
        capture_output=True,
        encoding="utf-8",
    ).stdout
    package = re.search(
        r"package: name='([^']+)' versionCode='(\d+)' versionName='([^']+)'", badging
    )
    if (
        not package
        or package[1] != "ru.cosmomine.edu_helper"
        or not re.fullmatch(r"\d+\.\d+\.\d+", package[3])
    ):
        raise RuntimeError("Unexpected APK package or version")
    version, build = package[3], int(package[2])
    with apk.open("rb") as stream:
        sha = hashlib.file_digest(stream, "sha256").hexdigest()
    name = f"eduhelper-{version}.apk"
    manifest = {
        "version": version,
        "build_number": build,
        "size": apk.stat().st_size,
        "sha256": sha,
        "signer_sha256": signer_hash,
        "apk_url": f"https://eduhelper.cosmomine.ru/downloads/{name}",
        "notes": args.notes,
    }
    credentials = dotenv_values(root / ".env")
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        credentials["SSH_ADDR"],
        username=credentials["SSH_USER"],
        password=credentials["SSH_PASS"],
        timeout=20,
    )
    try:
        with ssh.open_sftp() as sftp:
            base = "/var/www/eduhelper-downloads/"
            target = base + name
            try:
                with sftp.open(base + "android.json") as stream:
                    previous = json.load(stream)
                if previous["build_number"] > build:
                    raise RuntimeError("Refusing to downgrade the published release")
                if previous.get("signer_sha256", signer_hash) != signer_hash:
                    raise RuntimeError("APK must use the existing release signing key")
            except FileNotFoundError:
                pass
            try:
                sftp.stat(target)
            except FileNotFoundError:
                temporary = target + "." + uuid.uuid4().hex
                sftp.put(str(apk), temporary)
                sftp.posix_rename(temporary, target)
                with sftp.open(target + ".sha256", "w") as stream:
                    stream.write(sha + "  " + name + "\n")
            else:
                with sftp.open(target + ".sha256") as stream:
                    existing_hash = stream.read().decode().split()[0]
                if (
                    existing_hash != sha
                    or sftp.stat(target).st_size != apk.stat().st_size
                ):
                    raise RuntimeError(
                        "This version already exists with a different APK; increment the version"
                    )
            temporary = base + "android.json." + uuid.uuid4().hex
            with sftp.open(temporary, "w") as stream:
                stream.write(json.dumps(manifest, ensure_ascii=False))
            sftp.posix_rename(temporary, base + "android.json")
    finally:
        ssh.close()
    print(
        f"Published Android {version} ({build}), {manifest['size']} bytes, SHA-256 {sha}"
    )


if __name__ == "__main__":
    run()
