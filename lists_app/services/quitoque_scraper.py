"""
Fetch Quitoque recipe ingredient lists via headless Firefox (authenticated session).
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from django.conf import settings
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)


def _has_bold_class(c: Any) -> bool:
    if not c:
        return False
    parts = c if isinstance(c, list) else str(c).split()
    return "bold" in parts


INGREDIENT_UL_SELECTOR = "#ingredients-recipe .tab-pane#ingredients ul.ingredient-list"


class QuitoqueScraperError(Exception):
    """Base for scraper failures (message safe for API responses)."""

    def __init__(self, message: str, status_hint: int = 502):
        super().__init__(message)
        self.status_hint = status_hint


class QuitoqueLoginError(QuitoqueScraperError):
    def __init__(self, message: str = "Échec de la connexion Quitoque."):
        super().__init__(message, status_hint=401)


class QuitoqueParseError(QuitoqueScraperError):
    def __init__(
        self, message: str = "Impossible de lire les ingrédients sur la page."
    ):
        super().__init__(message, status_hint=502)


def validate_recipe_url(url: str) -> str:
    """
    Allow only HTTPS URLs on the configured Quitoque host.
    Returns normalized URL string or raises QuitoqueScraperError (400).
    """
    raw = (url or "").strip()
    if not raw:
        raise QuitoqueScraperError("URL manquante.", status_hint=400)
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        raise QuitoqueScraperError(
            "Seules les URL https sont acceptées.", status_hint=400
        )
    allowed = getattr(settings, "QUITOQUE_ALLOWED_HOST", "www.quitoque.fr").lower()
    if host != allowed:
        raise QuitoqueScraperError(
            f"URL non autorisée (hôte attendu : {allowed}).",
            status_hint=400,
        )
    return raw


def parse_ingredient_lis_from_html(html: str) -> list[dict[str, Any]]:
    """
    Parse “Dans votre box” ingredient list from full or partial page HTML.
    Used with driver.page_source in production and with fixtures in tests.
    """
    soup = BeautifulSoup(html, "html.parser")
    ul = soup.select_one(INGREDIENT_UL_SELECTOR)
    if ul is None:
        ul = soup.select_one("#ingredients-recipe ul.ingredient-list")
    if ul is None:
        return []

    items: list[dict[str, Any]] = []
    # Only direct <li> rows with quantity span (exclude nested structures)
    for li in ul.find_all("li", recursive=False):
        qty_span = li.find("span", class_=_has_bold_class)
        if not qty_span:
            continue
        quantity = qty_span.get_text(strip=True)
        name_container = qty_span.find_next_sibling("span")
        if name_container is None:
            name = ""
        else:
            name = name_container.get_text(separator=" ", strip=True)
        name = re.sub(r"\s+", " ", name).strip()
        if not name:
            continue
        items.append(
            {
                "name": name,
                "quantity": quantity,
                "notes": "",
                "section_slug": None,
            }
        )
    return items


def _login_path(url: str) -> str:
    return (urlparse(url).path or "/").rstrip("/") or "/"


def fetch_quitoque_ingredients(recipe_url: str) -> list[dict[str, Any]]:
    """
    Log in with QUITOQUE_EMAIL / QUITOQUE_PASSWORD, open recipe_url, return items.
    Raises QuitoqueScraperError subclasses on failure.
    """
    email = getattr(settings, "QUITOQUE_EMAIL", "") or ""
    password = getattr(settings, "QUITOQUE_PASSWORD", "") or ""
    if not email or not password:
        raise QuitoqueScraperError(
            "Import Quitoque désactivé : définissez QUITOQUE_EMAIL et QUITOQUE_PASSWORD.",
            status_hint=503,
        )

    recipe_url = validate_recipe_url(recipe_url)
    login_url = getattr(settings, "QUITOQUE_LOGIN_URL", "https://www.quitoque.fr/login")
    timeout = int(getattr(settings, "QUITOQUE_IMPORT_TIMEOUT", 60) or 60)

    opts = FirefoxOptions()
    opts.add_argument("-headless")
    opts.set_preference("dom.webnotifications.enabled", False)

    driver: webdriver.Firefox | None = None
    try:
        driver = webdriver.Firefox(options=opts)
        driver.set_page_load_timeout(timeout)

        driver.get(login_url)
        wait = WebDriverWait(driver, min(timeout, 45))

        wait.until(EC.presence_of_element_located((By.ID, "_username")))
        user_el = driver.find_element(By.ID, "_username")
        pass_el = driver.find_element(By.ID, "_password")

        user_el.clear()
        user_el.send_keys(email)
        pass_el.clear()
        pass_el.send_keys(password)

        form = driver.find_element(By.CSS_SELECTOR, 'form[action="/login-check"]')
        form.submit()

        try:
            WebDriverWait(driver, min(timeout, 45)).until(
                lambda d: _login_path(d.current_url) not in ("/login", "")
            )
        except TimeoutException as e:
            logger.warning("Quitoque login timeout")
            raise QuitoqueLoginError() from e

        if _login_path(driver.current_url) == "/login":
            raise QuitoqueLoginError()

        driver.get(recipe_url)
        try:
            WebDriverWait(driver, min(timeout, 45)).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, f"{INGREDIENT_UL_SELECTOR} li")
                )
            )
        except TimeoutException as e:
            logger.warning("Quitoque recipe ingredients not found")
            raise QuitoqueParseError() from e

        items = parse_ingredient_lis_from_html(driver.page_source)
        if not items:
            raise QuitoqueParseError()

        return items
    except QuitoqueScraperError:
        raise
    except WebDriverException as e:
        logger.exception("Quitoque WebDriver error")
        raise QuitoqueScraperError(
            "Navigateur d’import indisponible (Firefox / geckodriver).",
            status_hint=503,
        ) from e
    except Exception as e:
        logger.exception("Quitoque import failed")
        raise QuitoqueScraperError(
            "Échec de l’import Quitoque.",
            status_hint=502,
        ) from e
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                logger.debug("driver.quit() failed", exc_info=True)
