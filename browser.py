


def request(url: str):
    pass


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    args = parser.parse_args()
    request(args.url)

