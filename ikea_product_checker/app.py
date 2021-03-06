'''Ikea product avalability checker.
Checks via Ikea's "private" API, which
can be easily figured out via eny browser devtools.

Product is available for given store, sends an email.
'''
import sys
from typing import Any, Dict
from urllib.parse import urljoin

from requests import Response, Session
from requests.exceptions import HTTPError
from tomlkit import parse


def start_session() -> Session:
    """Starts session.
    Need to use this to first call ikea site to get cookies
    and stuff, so we can actually call backend database.

    Returns:
        Session: requests session object
    """
    return Session()


def load_config(filepath: str) -> Dict[str, Any]:
    """Returns parsed .toml file as `dict`

    Args:
        filepath (str): path to file

    Returns:
        Dict[str, Any]: parsed file content
    """
    with open(filepath, mode="r", encoding="utf-8") as file:
        return parse(file.read())


def fetch_product_info(
    sess: Session,
    api_host: str,
    api_resource: str,
    store_code: str,
    product_code: str,
    resource_header: Dict[str, str],
) -> Dict[str, Any]:
    """Sends GET request for given product_code in store and returns
    parsed body as `dict`.

    Args:
        api_host (str): API host url
        api_resource (str): api resource
        store_code (str): code of the store
        product_code (str): code of the product

    Returns:
        Dict[str, Any]: information about product
    """
    try:
        resource: str = api_resource.replace("{store_code}", store_code).replace(
            "{product_code}", product_code
        )
        response: Response = sess.get(
            urljoin(
                api_host,
                resource,
            ),
            headers=resource_header,
        )
        response.raise_for_status()
        return response.json()
    except HTTPError as exc:
        print(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    config: Dict[str, Any] = load_config("config.toml")
    session: Session = start_session()
    print(
        fetch_product_info(
            session,
            config["ikea"]["api"]["host"],
            config["ikea"]["api"]["resources"]["availability"],
            config["ikea"]["store_codes"]["praha_cerny_most"],
            config["ikea"]["product_codes"]["hattefjaell_grey"],
            config["ikea"]["headers"]["availability"],
        )
    )
