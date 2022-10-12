import subprocess


def genkey():
    return subprocess.run(
        ["wg", "genkey"], stdout=subprocess.PIPE, check=True, text=True
    ).stdout.strip()


def pubkey(private_key):
    return subprocess.run(
        ["wg", "pubkey"],
        input=private_key,
        stdout=subprocess.PIPE,
        check=True,
        text=True,
    ).stdout.strip()


def genpsk():
    return subprocess.run(
        ["wg", "genpsk"], stdout=subprocess.PIPE, check=True, text=True
    ).stdout.strip()


def gen_key_pair():
    private_key = genkey()
    public_key = pubkey(private_key)
    return private_key, public_key
