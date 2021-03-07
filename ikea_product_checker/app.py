'''Ikea product avalability checker.
Checks via Ikea's "private" API, which
can be easily figured out via eny browser devtools.

Product is available for given store, sends an email.
'''
import sys
from typing import Any, Dict, List
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


def is_available(data: Dict[str, Any]) -> bool:
    """Predicate. Is product in stock or not?

    Args:
        data (Dict[str, Any]): returned data for queried product via api call

    Returns:
        bool: `true` if available, else `false`
    """
    stock_count: str = data["StockAvailability"]["RetailItemAvailability"][
        "AvailableStock"
    ]["$"]
    return int(stock_count) > 0


def prep_forecast_message(data: Dict[str, Any]) -> str:
    """Creates string with information about
    expected availability of the product

    Args:
        data (Dict[str, Any]): data returned from api call

    Returns:
        str: formatted string info
    """

    def _pad_left(string: str, how_much: int = 5, pad_char=" ") -> str:
        return string.rjust(len(string) + how_much, pad_char)

    forecast: List[Dict[str, Any]] = data["StockAvailability"][
        "AvailableStockForecastList"
    ]["AvailableStockForecast"]

    message: str = "Availability Forecast:\n\n".upper()

    for day in forecast:
        for key, value in list(day.items()):
            message += f"{_pad_left(key)}: {value['$']}\n\r"
        message += "\n==========\n\n"

    return message


def main():
    """Main func."""
    config: Dict[str, Any] = load_config("config.toml")
    session: Session = start_session()

    product: Dict[str, Any] = fetch_product_info(
        session,
        config["ikea"]["api"]["host"],
        config["ikea"]["api"]["resources"]["availability"],
        config["ikea"]["store_codes"]["praha_cerny_most"],
        config["ikea"]["product_codes"]["hattefjaell_grey"],
        config["ikea"]["headers"]["availability"],
    )

    print(is_available(product))
    print(prep_forecast_message(product))


if __name__ == "__main__":
    main()
