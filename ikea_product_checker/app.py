"""Ikea product avalability checker.
Checks via Ikea's "private" API, which
can be easily figured out via eny browser devtools.

Can notify via email - in this case via SendPulse free of charge
service, but you have to configure it yourself.
By default it is commented out.
"""
import sys
from typing import Any, Dict, List, Tuple
from urllib.parse import urljoin

from requests import Response, Session
from requests.exceptions import HTTPError
from tomlkit import parse
from tqdm import tqdm
from pysendpulse.pysendpulse import PySendPulse


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


def is_available(data: Dict[str, Any]) -> Tuple[bool, str]:
    """Predicate. Is product in stock or not?

    Args:
        data (Dict[str, Any]): returned data for queried product via api call

    Returns:
        bool: `true` if available, else `false`
    """
    stock_count: str = data["StockAvailability"]["RetailItemAvailability"][
        "AvailableStock"
    ]["$"]
    return (int(stock_count) > 0, stock_count)


def prep_product_message(
    store_name: str,
    product_name: str,
    availability_status: Tuple[bool, str],
    forecast: List[Dict[str, Any]],
) -> str:
    """Returns email message str for given product

    Args:
        store_name (str): name of the store
        product_name (str): name of the product
        availability_status (Tuple[bool, str]): availability info
        forecast (List[Dict[str, Any]]): forecast data

    Returns:
        str: formatted message str
    """

    def _pad_left(string: str, how_much: int = 5, pad_char=" ") -> str:
        return string.rjust(len(string) + how_much, pad_char)

    message: str = f"Store: '{store_name}'\n".upper()
    message += f"Status for '{product_name}':\n\n"
    # pylint:disable= line-too-long
    message += f"Product is currently {'available' if availability_status[0] else 'not available'} with {availability_status[1]} in stock.\n\n"
    # pylint: enable= line-too-long
    message += "Availability Forecast:\n\n".upper()

    for day in forecast:
        for key, value in list(day.items()):
            message += f"{_pad_left(key)}: {value['$']}\n\r"
        message += "\n==========\n\n"

    return message


def check_products(config: Dict[str, Any], session: Session) -> List[Dict[str, Any]]:
    """Checks all defined products for data and returns
    list of dicts containing:

    - name of the store
    - name of the product
    - whehter the product is available
    - availability forecast data of the product

    Args:

        config (Dict[str, Any]): content of config file
        session (Session): requests Session class instance

    Returns:
        List[Dict[str, Any]]: data for further processing
    """
    output: List[Dict[str, Any]] = []
    stores: Dict[str, str] = config["ikea"]["store_codes"]
    products: Dict[str, str] = config["ikea"]["product_codes"]

    for store_name, store_code in tqdm(
        list(stores.items()), colour="blue", desc="Processing stores"
    ):
        for product_name, product_code in tqdm(
            list(products.items()), colour="green", desc="Processing products"
        ):
            data: Dict[str, Any] = fetch_product_info(
                session,
                config["ikea"]["api"]["host"],
                config["ikea"]["api"]["resources"]["availability"],
                store_code,
                product_code,
                config["ikea"]["headers"]["availability"],
            )
            status: Tuple[bool, str] = is_available(data)
            output.append(
                {
                    "store": store_name.replace("_", " "),
                    "name": product_name.replace("_", " ").capitalize(),
                    "status": status,
                    "forecast": data["StockAvailability"]["AvailableStockForecastList"][
                        "AvailableStockForecast"
                    ],
                }
            )

    return output


def create_mail_message(products_data: List[Dict[str, Any]]) -> str:
    """Creates the whole message and returns.

    Args:
        products_data (List[Dict[str, Any]]): data of products we want to output

    Returns:
        str: message we want to sent, formatted
    """
    message: str = "Availability status of IKEA products:\n\n".upper()

    for product in products_data:
        message += prep_product_message(
            product["store"], product["name"], product["status"], product["forecast"]
        )

    return message


def send_email(message: str) -> Dict[str, Any]:
    """Sends email.
    All configs are private, ofc.

    Args:
        message (str): email message.
    """
    mail_config: Dict[str, str] = load_config(".mail.config.toml")

    proxy: PySendPulse = PySendPulse(
        mail_config["REST_API_ID"],
        mail_config["REST_API_SECRET"],
        mail_config["TOKEN_STORAGE"],
        memcached_host=mail_config["MEMCACHED_HOST"],
    )
    email = {
        "subject": "IKEA product availability update",
        "html": "",
        "text": message,
        "template": {"id": mail_config["TEMPLATE_ID"]},
        "from": {"name": mail_config["NAME"], "email": mail_config["SENDER"]},
        "to": [{"name": mail_config["NAME"], "email": mail_config["SENDER"]}],
        "bcc": [],
    }
    return proxy.smtp_send_mail(email)


def main():
    """Main func."""
    config: Dict[str, Any] = load_config("config.toml")
    session: Session = start_session()
    products_data: List[Dict[str, Any]] = check_products(config, session)
    message: str = create_mail_message(products_data)
    print(message)
    # print(send_email(message))


if __name__ == "__main__":
    main()
