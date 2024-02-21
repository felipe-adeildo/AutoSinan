import json
import os
import re
from pathlib import Path
from typing import List

import pandas as pd
from bs4 import NavigableString, Tag
from dbfread import DBF

from core.constants import CREDENTIALS_FILE


def clear_screen():
    """Clear the console screen"""
    os.system("cls" if os.name == "nt" else "clear")


def load_data(path: Path) -> pd.DataFrame:
    """Load data from file

    Args:
        path (Path): Path to file.
            Allowed extensions: `.csv`, `.xlsx`, `.dbf`

    Raises:
        ValueError: Unsupported file type

    Returns:
        pd.DataFrame: Dataframe with loaded data
    """
    ext = path.suffix
    match ext:
        case ".csv":
            return pd.read_csv(path, sep=";", encoding="latin-1")
        case ".xlsx":
            return pd.read_excel(path)
        case ".dbf":
            return pd.DataFrame(iter(DBF(path, encoding="latin-1")))
        case _:
            raise ValueError(f"Unsupported file type: {ext}")


def normalize_name(name: str) -> str:
    """Normalize name (string) to the same format (upper and no spaces)

    Args:
        name (str): Name to normalize

    Returns:
        str: Normalized name
    """
    if not isinstance(name, str):
        return name
    return re.sub(r"\s+", " ", name).strip().upper()


def normalize_columns(df: pd.DataFrame, columns: List[str]):
    """Inplace normalization of columns

    Args:
        df (pd.DataFrame): Dataframe with columns to normalize
        columns (List[str]): List of columns to normalize
    """
    for column in columns:
        df[column] = df[column].apply(lambda x: normalize_name(x))


def to_datetime(df: pd.DataFrame, columns: List[str], **kw):
    """Inplace conversion of columns to datetime

    Args:
        df (pd.DataFrame): Dataframe with columns to convert
        columns (List[str]): List of columns to convert
        **kw: Keyword arguments to pass to pd.to_datetime
    """
    for column in columns:
        df[column] = pd.to_datetime(df[column], **kw)


def valid_tag(tag: Tag | NavigableString | None) -> Tag | None:
    if not tag or isinstance(tag, NavigableString):
        return None
    return tag


def get_sinan_credentials():
    """Get Sinan credentials from file or from user input

    Returns:
        dict: A dictionary with `username` and `password` keys
    """
    credentials_path = Path(CREDENTIALS_FILE)
    if credentials_path.exists():
        with credentials_path.open() as f:
            credentials = json.load(f)
    else:
        credentials = {
            "username": input("Seu usuário: "),
            "password": input("Sua senha: "),
        }
        with credentials_path.open("w") as f:
            json.dump(credentials, f, indent=4)

    return credentials
