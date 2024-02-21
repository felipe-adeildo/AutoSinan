import requests
from bs4 import BeautifulSoup

from core.abstract import Bot
from core.constants import SINAN_BASE_URL, USER_AGENT
from core.utils import valid_tag
from investigation.data_loader import SinanGalData
from investigation.investigator import Investigator
from investigation.notification_researcher import NotificationResearcher


class InvestigationBot(Bot):
    """Sinan client taht will be used to interact with the Sinan Website doing things like:
    - Login
    - Filling out forms
    - Verifying submitted forms
    """

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password

        self._init_apps()

    def __create_data_manager(self):
        self.data = SinanGalData()
        self.data.load()

    def __create_session(self):
        self.session = requests.session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def __create_notification_researcher(self):
        # TODO: move the agravo to a settings.toml file
        self.researcher = NotificationResearcher(self.session, "A90 - DENGUE")

    def __create_investigator(self):
        self.investigator = Investigator(self.session)

    def _init_apps(self):
        initializators = [
            self.__create_session,
            self.__create_notification_researcher,
            self.__create_investigator,
            self.__create_data_manager,
        ]

        for fn in initializators:
            fn()

    def __verify_login(self, res: requests.Response):
        soup = BeautifulSoup(res.content, "html.parser")
        if not soup.find("div", {"id": "detalheUsuario"}):
            print("Login failed.")
            exit(1)

        # update the apps that use the session
        need_session = [self.researcher, self.investigator]
        for app in need_session:
            setattr(app, "session", self.session)

    def _login(self):
        print("Logando no SINAN...")
        self.__create_session()

        # set JSESSIONID
        res = self.session.get(f"{SINAN_BASE_URL}/sinan/login/login.jsf")

        soup = BeautifulSoup(res.content, "html.parser")
        form = valid_tag(soup.find("form"))
        if not form:
            print("Login Form not found.")
            exit(1)

        inputs = form.find_all("input")
        payload = dict()
        for input_ in inputs:
            name, value = input_.get("name"), input_.get("value")
            if "username" in name:
                value = self._username
            elif "password" in name:
                value = self._password
            payload[name] = value

        res = self.session.post(
            f"{SINAN_BASE_URL}{form.get('action')}",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.__verify_login(res)
        print("Logado com sucesso.")

    def start(self):
        self._login()

        patients = []  # TODO: get this from the data loader
        for patient_name in patients:
            sinan_response = self.researcher.search(patient_name)
            match len(sinan_response):
                case 0:
                    print("Nenhum resultado encontrado.")
                case 1:
                    sinan_response = next(iter(sinan_response))
                    self.investigator.investigate({}, sinan_response)
                case _:
                    print("Múltiplos resultados encontrados:")
