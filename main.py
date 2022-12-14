from typing import Dict, Optional, TypedDict, List
from threading import Thread, main_thread
from getpass import getpass
import argparse
import datetime
import time

from pynput import keyboard
from pynput.keyboard import Key
import requests


class UpDownData(TypedDict):
    time: float
    name: str
    total_down: int
    total_up: int
    down: int
    up: int
    first_total_down: int
    first_total_up: int
    first_time: float
    time_interval: int  # time interval with the previous request


class Load:
    """get users upload/download from X-UI APIs and show charts"""

    def __init__(self, panel_ip_address: str, panel_username: str, panel_password: str) -> None:
        self.panel_ip_address = panel_ip_address.rstrip("/")
        self.panel_username = panel_username
        self.panel_password = panel_password
        self.requests_session = requests.Session()
        self.login_session = None

        self.active_chart: int = None
        self.users_up_down_time_line: Dict[str, List[UpDownData]] = {}

        self.main_window_update_sleep = 0.01
        self.get_data_update_sleep = 8
        self.chart_time_line_len = 45
        self.chart = []
        self.itrate_count = 0
        self.page_nuumber_line = ""
        self.chart_log_line = ""

    def login(self):
        try:
            res = self.requests_session.post(
                f"{self.panel_ip_address}/login/",
                data={"username": self.panel_username, "password": self.panel_password},
                timeout=3,
            )

            if res.ok and (res.json())["success"] == True:
                self.login_session = res.cookies.get("session")
                return True

            return False

        except Exception as e:
            print("error-5:", e)
            return False

    def lop_get_update(self):
        while main_thread().is_alive():
            self._update()
            self._clear_old_datas()
            time.sleep(self.get_data_update_sleep)

    def lop_show_main_window(self):
        while main_thread().is_alive():
            try:
                names = list(self.users_up_down_time_line.keys())
                if self.active_chart is None:
                    self.active_chart = 0
                self._create_chart(names[self.active_chart])
                self._show_chart()
                time.sleep(self.main_window_update_sleep)

            except IndexError:
                time.sleep(self.main_window_update_sleep)

    def _update(self):
        """call `/xui/inbound/list` api and save new data"""

        try:
            res = self.requests_session.post(
                f"{self.panel_ip_address}/xui/inbound/list",
                cookies={"session": self.login_session},
                timeout=2,
            )

            if res.ok and (data := res.json())["success"] == True:

                up_down_datas = self._extract_request_data(data["obj"])
                self._append_to_users_up_down_time_line(up_down_datas)
                return

            self.chart_log_line = f"error-1: {res.status_code}"

        except Exception as e:
            self.chart_log_line = f"error-1: {e}"
            time.sleep(1)

    def _extract_request_data(self, datas) -> List[UpDownData]:

        up_down_datas: List[UpDownData] = []

        now = time.time()

        for data in datas:
            name = f"{data['id']:0=2}-{data['remark']}"
            total_down = data["down"]
            total_up = data["up"]
            down = total_down - (self._user_previous_down_up(name, "total_down") or total_down)
            up = total_up - (self._user_previous_down_up(name, "total_up") or total_up)
            time_interval = (now - (self._user_previous_down_up(name, "time") or now)) + 0.001

            update_data = UpDownData(
                time=now,
                name=name,
                total_down=total_down,
                total_up=total_up,
                down=down,
                up=up,
                first_total_down=self._user_previous_down_up(name, "first_total_down") or total_down,
                first_total_up=self._user_previous_down_up(name, "first_total_up") or total_up,
                first_time=self._user_previous_down_up(name, "first_time") or now,
                time_interval=time_interval,
            )
            up_down_datas.append(update_data)

        return up_down_datas

    def _append_to_users_up_down_time_line(self, up_down_datas: List[UpDownData]):
        for up_down_data in up_down_datas:

            if up_down_data["name"] not in self.users_up_down_time_line:
                self.users_up_down_time_line[up_down_data["name"]] = []

            self.users_up_down_time_line[up_down_data["name"]].append(up_down_data)

    def _clear_old_datas(self):

        for user, user_up_down_time_line in self.users_up_down_time_line.items():
            if len(user_up_down_time_line) > self.chart_time_line_len:
                self.users_up_down_time_line[user].pop(0)

    def _user_max_up_down_in_time_line(self, user_up_down_time_line: List[UpDownData]) -> int:
        max_up_down = 0

        for data in user_up_down_time_line:

            sum_up_and_down = data["up"] + data["down"]

            if sum_up_and_down > max_up_down:
                max_up_down = sum_up_and_down

        return max_up_down

    def _user_previous_down_up(self, name, filed) -> Optional[UpDownData]:
        if name in self.users_up_down_time_line:
            return self.users_up_down_time_line[name][-1][filed]
        return None

    def _user_last_total_down(self, name: str) -> Optional[UpDownData]:

        if name in self.users_up_down_time_line:
            user_last_up_down_time_line = self.users_up_down_time_line[name][-1]
            return user_last_up_down_time_line["total_down"]
        return None

    def _user_last_total_up(self, name: str) -> Optional[UpDownData]:

        if name in self.users_up_down_time_line:
            user_last_up_down_time_line = self.users_up_down_time_line[name][-1]
            return user_last_up_down_time_line["total_up"]
        return None

    def _create_chart(self, user_name: str):

        user_up_down_time_line: List[UpDownData] = self.users_up_down_time_line[user_name]
        last_up_down = user_up_down_time_line[-1]
        user_max_up_down = self._user_max_up_down_in_time_line(user_up_down_time_line)
        user_max_up_down = int(user_max_up_down // last_up_down["time_interval"])

        self.chart: List[List[str]] = [
            [user_max_up_down],  # line 1
            [int(user_max_up_down * 0.9)],  # line 2
            [int(user_max_up_down * 0.8)],  # line 3
            [int(user_max_up_down * 0.7)],  # line 4
            [int(user_max_up_down * 0.6)],  # line 5
            [int(user_max_up_down * 0.5)],  # line 6
            [int(user_max_up_down * 0.4)],  # line 7
            [int(user_max_up_down * 0.3)],  # line 8
            [int(user_max_up_down * 0.2)],  # line 9
            [0],  # line 10
        ]

        for user_up_down in user_up_down_time_line:
            for i in range(0, 10):
                user_sum_down_up = user_up_down["down"] + user_up_down["up"]
                user_sum_down_up_per_second = user_sum_down_up // last_up_down["time_interval"]

                if user_sum_down_up_per_second != 0 and user_sum_down_up_per_second >= int(self.chart[i][0]):
                    self.chart[i].append("#")
                else:
                    self.chart[i].append(".")

        self.chart.append(list(f" {'-' * self.chart_time_line_len}"))  # line 11

        self.chart.append(list(f" [down + up] / second"))  # line 13
        self.chart.append(list(" "))  # line 14
        self.chart.append(list(f" {'user':6}:   {user_name}"))  # line 15
        self.chart.append(
            list(
                f" {'total':6}:   "
                f"D: {self._sizeof_fmt(last_up_down['total_down'] - last_up_down['first_total_down'])}  "
                f"U: {self._sizeof_fmt(last_up_down['total_up'] - last_up_down['first_total_up'])} "
                f"in {str(datetime.timedelta(seconds=round((last_up_down['time'] - last_up_down['first_time']))))} "
            )
        )  # line 16
        self.chart.append(
            list(
                f" {'speed':6}:   "
                f"D: {self._sizeof_fmt(int(last_up_down['down'] // last_up_down['time_interval']))}/S  "
                f"U: {self._sizeof_fmt(int(last_up_down['up'] // last_up_down['time_interval']))}/S"
            )
        )  # line 17
        self.chart.append(list(f" {'last update':6}:   {int(time.time() - last_up_down['time'])} S ago"))  # line 18
        self.chart.append(list(" "))  # line 19
        self.chart.append(list(" use arrow keys for change user. ( <-  -> )"))  # line 20
        self.chart.append(list(" " + str(self.page_nuumber_line)))  # 21
        self.chart.append(list(" " + str(self.chart_log_line)))  # 22

    @staticmethod
    def clear_one_line():
        LINE_UP = "\033[1A"  # The ANSI code that is assigned to LINE_UP indicates that the cursor should move up a single line.
        LINE_CLEAR = (
            "\x1b[2K"  # The ANSI code that is assigned to `LINE_CLEAR` erases the line where the cursor is located.
        )
        print(LINE_UP, end=LINE_CLEAR)

    def _clear_chart(self):
        for _ in self.chart:
            self.clear_one_line()

    def _sizeof_fmt(self, size):
        if type(size) == int:
            for unit in ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]:
                if size < 1024.0 or unit == "PiB":
                    break
                size /= 1024.0
            return f"{size:.{2}f} {unit}"
        return size

    def _show_chart(self):
        """clear last page_template lines and print page_template by new args"""

        if self.itrate_count > 0:
            self._clear_chart()
        self.itrate_count += 1

        for chart_line in self.chart:
            size = self._sizeof_fmt(chart_line[0])
            line = f"{size:15}{''.join(chart_line[1:])}"
            print(line)

    def on_press_key(self, key):
        names = list(self.users_up_down_time_line.values())

        if key == Key.right:
            if not self.active_chart >= len(names) - 1:
                self.active_chart += 1

        elif key == Key.left:
            if not self.active_chart == 0:
                self.active_chart -= 1

        self.page_nuumber_line = f" {self.active_chart} / {len(names) - 1}"

        LINE_CLEAR = (
            "\x1b[2K"  # The ANSI code that is assigned to `LINE_CLEAR` erases the line where the cursor is located.
        )
        print("", end=LINE_CLEAR)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        prog="python3 main.py",
        description="teminal user load panel for X-UI project (xray)",
    )

    parser.add_argument("-a", "--address", help="panel address, example: `http://localhost:54321`", required=True)
    parser.add_argument("-u", "--username", help="panel username", required=True)
    args = parser.parse_args()

    panel_password = getpass("password: ")
    Load.clear_one_line()

    load = Load(panel_ip_address=args.address, panel_username=args.username, panel_password=panel_password)

    # login to panel
    ok = load.login()
    if not ok:
        print("error-3: login failed")
        exit(-1)

    Thread(target=load.lop_get_update).start()  # start lop for get update from server
    Thread(target=load.lop_show_main_window).start()  # start lop for show chart

    # bind arrow keys to on_press_key function
    with keyboard.Listener(on_press=load.on_press_key) as listener:
        listener.join()
