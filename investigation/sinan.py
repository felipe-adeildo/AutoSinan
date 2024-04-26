from datetime import datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup

from core.abstract import Bot
from core.constants import (
    EXAMS_GAL_MAP,
    SCRIPT_GENERATED_PATH,
    SINAN_BASE_URL,
    TODAY,
    USER_AGENT,
)
from core.utils import create_logger, valid_tag
from investigation.data_loader import SinanGalData
from investigation.investigator import Investigator
from investigation.notification_researcher import NotificationResearcher


class InvestigationBot(Bot):
    """Sinan client taht will be used to interact with the Sinan Website doing things like:
    - Login
    - Filling out forms
    - Verifying submitted forms
    """

    def __init__(self, settings: dict) -> None:
        self._username = settings["sinan_credentials"]["username"]
        self._password = settings["sinan_credentials"]["password"]
        self._settings = settings
        self.logger = create_logger("investigação")

        self._init_apps()

    def __create_data_manager(self):
        """Load data from SINAN and GAL datasets"""
        self.logger.info("APP_FACTORY: Gerenciador de Dados")
        self.data = SinanGalData(self.logger)
        self.data.load()
        self.logger.info("APP_FACTORY: Gerenciador de Dados criado")
        # self.data.df.to_excel("base_unificada.xlsx", index=False)

    def __create_session(self):
        """Create a session agent that will be used to make requests"""
        self.logger.info("APP_FACTORY: Sessão de Requisição")
        self.session = requests.session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.logger.info("APP_FACTORY: Sessão de Requisição criada")

    def __create_notification_researcher(self):
        """Create a notification searcher that will be used to research notifications given a patient"""
        self.logger.info("APP_FACTORY: Pesquisador de Notificação")
        agravo = self._settings["sinan_investigacao"]["agravo"]
        self.researcher = NotificationResearcher(self.session, agravo, self.logger)
        self.logger.info("APP_FACTORY: Pesquisador de Notificação criado")

    def __create_investigator(self):
        """Create an Investigator that will be used to investigate (fill data)"""
        self.logger.info("APP_FACTORY: Investigador")
        self.investigator = Investigator(self.session, self.logger)
        self.logger.info("APP_FACTORY: Investigador criado")

    def _init_apps(self):
        """Factory method to initialize the apps"""
        self.logger.info("Iniciando aplicativos")
        initializators = [
            self.__create_session,
            self.__create_notification_researcher,
            self.__create_investigator,
            self.__create_data_manager,
        ]

        for fn in initializators:
            fn()

        self.logger.info("Aplicativos iniciados")

    def __verify_login(self, res: requests.Response):
        """Verify if the login was successful

        Args:
            res (requests.Response): The response from the sinan website
        """
        soup = BeautifulSoup(res.content, "html.parser")
        if not soup.find("div", {"id": "detalheUsuario"}):
            self.logger.error("LOGIN: Falha na autenticação.")
            print("Falha no Login")
            exit(1)

        self.logger.info("LOGIN: Autenticação concluída.")

        # update the apps that use the session
        need_session = [self.researcher, self.investigator]
        for app in need_session:
            setattr(app, "session", self.session)

    def _login(self):
        """Login to the Sinan Website"""
        self.logger.info("LOGIN: Logando no SINAN")
        print("Logando no SINAN...")

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

    def __fill_form(self, patient: pd.Series):
        """Fill out the form with the patient data

        Args:
            patient (dict): The patient data
        """
        print(f"Preenchendo investigação do paciente {patient['Paciente']}...")
        sinan_response = self.researcher.search(patient.to_dict())
        open_payloads = [r["open_payload"] for r in sinan_response]
        done_data = []
        match len(sinan_response):
            case 0:
                self.logger.warning(
                    f"FILL_FORM: Nenhum resultado encontrado para {patient['Paciente']}."
                )
                print("Nenhum resultado encontrado para este paciente.")
            case 1:
                open_payload = next(iter(open_payloads))
                result = self.investigator.investigate(patient.to_dict(), open_payload)
                done_data.append(result)
            case _:
                self.logger.warning(
                    f"FILL_FORM: Multiplos resultados encontrados para {patient['Paciente']}."
                )
                result = self.investigator.investigate_multiple(
                    patient.to_dict(), open_payloads
                )
                done_data.extend(result or [])

        return done_data

    def start(self):
        self.logger.info("INICIANDO INVESTIGACAO")
        self._login()
        progress_data = []
        release_date = datetime.strptime(
            input("Data de liberação (dd/mm/aaaa): "), "%d/%m/%Y"
        )
        tests = map(lambda e: EXAMS_GAL_MAP[e], self.data.df["Exame"].unique())
        run_datetime = TODAY.strftime("%d.%m.%Y %H-%M")
        log_filename = f"Investigação ({', '.join(tests)}) - liberação {release_date.strftime('%d.%m.%Y %H-%M')} - ({run_datetime}).xlsx"
        for _, patient in self.data.df.iterrows():
            done_data = self.__fill_form(patient)
            progress_data.extend(done_data)
            df = pd.DataFrame(progress_data)
            df.to_excel(SCRIPT_GENERATED_PATH / log_filename, index=False)
