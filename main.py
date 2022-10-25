from typing import Dict, Optional, TypedDict, List
import time
from threading import Thread

import requests
from pynput import keyboard
from pynput.keyboard import Key

# Change these:

IP = "http://localhost:54321"  # x-ui pannel ip:port
USERNAME = ""  # panel user
PASSWORD = ""  # panel pass


class UpDownData(TypedDict):
    time: float
    name: str
    total_down: int
    total_up: int
    down: int
    up: int
    first_total_down: int
    first_total_up: int


class Load:
    """get users upload/download from X-UI APIs and show charts"""

    def __init__(self) -> None:
        self.requests_session = requests.Session()
        self.login_session = None
        self.active_chart: int = None
        self.users_up_down_time_line: Dict[str, List[UpDownData]] = {}
        self.main_window_update_sleep = 0.1
        self.get_data_update_sleep = 8
        self.chart_time_line_len = 20
        self.chart = []
        self.itrate_count = 0

    def login(self):
        try:
            res = self.requests_session.post(
                f"{IP}/login/",
                data={"username": USERNAME, "password": PASSWORD},
                timeout=2,
            )

            if res.ok and (res.json())["success"] == True:
                self.login_session = res.cookies.get("session")
                return True

            return False

        except KeyboardInterrupt as e:
            print("error-5:", e)
            return False

    def lop_update(self):
        while True:
            self._update()
            self._clear_old_datas()
            time.sleep(self.get_data_update_sleep)

    def main_window(self):
        while True:
            try:
                names = list(self.users_up_down_time_line.keys())
                if self.active_chart is None:
                    self.active_chart = 0
                self._create_chart(names[self.active_chart])
                self._show_chart()
                time.sleep(self.main_window_update_sleep)
            except:
                time.sleep(1)

    def _update(self):
        """call `/xui/inbound/list` api and save new data"""

        try:
            res = self.requests_session.post(
                f"{IP}/xui/inbound/list",
                cookies={"session": self.login_session},
                timeout=2,
            )

            if res.ok and (data := res.json())["success"] == True:

                up_down_datas = self._extract_request_data(data["obj"])
                self._append_to_users_up_down_time_line(up_down_datas)
                return

            print("error-1:", res.status_code)

        except KeyboardInterrupt as e:
            print("error-2:", e)

    def _extract_request_data(self, datas) -> List[UpDownData]:

        up_down_datas: List[UpDownData] = []

        now = time.time()

        for data in datas:
            name = f"{data['id']:0=2}-{data['remark']}"
            total_down = data["down"]
            total_up = data["up"]
            down = total_down - (
                self._user_last_down_up(name, "total_down") or total_down
            )
            up = total_up - (self._user_last_down_up(name, "total_up") or total_up)

            update_data = UpDownData(
                time=now,
                name=name,
                total_down=total_down,
                total_up=total_up,
                down=down,
                up=up,
                first_total_down=self._user_last_down_up(name, "first_total_down")
                or total_down,
                first_total_up=self._user_last_down_up(name, "first_total_up")
                or total_up,
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

    def _user_max_up_or_down_in_time_line(
        self, user_up_down_time_line: List[UpDownData]
    ) -> int:
        max_up_or_down = 0

        for data in user_up_down_time_line:

            if data["up"] > max_up_or_down:
                max_up_or_down = data["up"]

            if data["down"] > max_up_or_down:
                max_up_or_down = data["down"]

        return max_up_or_down

    def _user_last_down_up(self, name, filed) -> Optional[UpDownData]:
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

        user_up_down_time_line: List[UpDownData] = self.users_up_down_time_line[
            user_name
        ]
        user_max_up_down = self._user_max_up_or_down_in_time_line(
            user_up_down_time_line
        )

        self.chart: List[List[str]] = [
            [user_max_up_down],  # 1
            [int(user_max_up_down * 0.9)],  # 2
            [int(user_max_up_down * 0.8)],  # 3
            [int(user_max_up_down * 0.7)],  # 4
            [int(user_max_up_down * 0.6)],  # 5
            [int(user_max_up_down * 0.5)],  # 6
            [int(user_max_up_down * 0.4)],  # 7
            [int(user_max_up_down * 0.3)],  # 8
            [int(user_max_up_down * 0.2)],  # 9
            [0],  # 10
        ]

        for user_up_down in user_up_down_time_line:
            for i in range(0, 10):
                self.chart[i].append(" ")
                self.chart[i].append(
                    "#" if user_up_down["down"] > int(self.chart[i][0]) else "."
                )
                self.chart[i].append(
                    "#" if user_up_down["up"] > int(self.chart[i][0]) else "."
                )

        last_up_down = user_up_down_time_line[-1]

        self.chart.append(list(f" {' __' * self.chart_time_line_len}"))
        self.chart.append(list(f" [down-up] / {self.get_data_update_sleep} S"))
        self.chart.append(list(" "))
        self.chart.append(list(f" {'user':6}:   {user_name}"))
        self.chart.append(
            list(
                f" {'total':6}:   D: {self._sizeof_fmt(last_up_down['total_down'] - last_up_down['first_total_down'])}/S  U: {self._sizeof_fmt(last_up_down['total_up'] - last_up_down['first_total_up'])} / S "
            )
        )
        self.chart.append(
            list(
                f" {'speed':6}:   D: {self._sizeof_fmt(last_up_down['down'] // self.get_data_update_sleep +1 )}/S  U: {self._sizeof_fmt(last_up_down['up'] // self.get_data_update_sleep +1)} / S"
            )
        )
        self.chart.append(list(f" {'time':6}:   {last_up_down['time']}"))
        self.chart.append(list(" "))
        self.chart.append(list(" use arrow keys for change user. ( <-  -> )"))

    def _clear_chart(self):
        LINE_UP = "\033[1A"  # The ANSI code that is assigned to LINE_UP indicates that the cursor should move up a single line.
        LINE_CLEAR = "\x1b[2K"  # The ANSI code that is assigned to `LINE_CLEAR` erases the line where the cursor is located.

        for _ in self.chart:
            print(LINE_UP, end=LINE_CLEAR)

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
            self.active_chart += 1
            return

        if key == Key.left:
            self.active_chart -= 1
            return

        LINE_CLEAR = "\x1b[2K"  # The ANSI code that is assigned to `LINE_CLEAR` erases the line where the cursor is located.
        print("", end=LINE_CLEAR)


if __name__ == "__main__":

    load = Load()

    # login to panel
    ok = load.login()
    if not ok:
        print("error-3: login failed")
        exit(-1)

    Thread(target=load.lop_update).start()  # start lop for get update from server
    Thread(target=load.main_window).start()  # start lop for show chart

    # bind arrow keys to on_press_key function
    with keyboard.Listener(on_press=load.on_press_key) as listener:
        listener.join()
