from lxml import etree


class TCXModifier:
    def __init__(self, file_path: str):
        self.tree = etree.parse(file_path)

    def save(self, file_path: str) -> None:
        """
        Save current state of xml
        :param file_path: file path to save
        :return:
        """
        self.tree.write(
            file_path,
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8",
        )

    def speedup(self, multiplier: float) -> None:
        """
        Method modifies tcx data: TotalTimeSeconds, MaximumSpeed, Speed, Time
        :param multiplier: value to speedup. i.e. 1.1 means, 10% speedup
        :return:
        """
        pass

    def cleanup_heart_rate(self, max_hr: int) -> None:
        pass

    def cleanup_power(self, max_power: float) -> None:
        """
        If power > max_power - set power to zero. Sometimes powermeter calculates unreal values like 2kW for 1 second when cyclist do not pedal at all

        :param max_power: higher power values will be treated as mistake and set to 0
        :return:
        """
        pass

    def cleanup_canence(self, max_canence: float) -> None:
        """
        If cadence > max_cadence - set cadence to zero. Sometimes megnetice cadence sensor calculates unreal values like 200rpm for 1 second when cyclist do not pedal at all

        :param max_canence: higher cadence values will be treated as mistake and set to 0
        :return:
        """
        pass

    def update_start_time(self, start_time: str) -> None:
        """
        Set start time and move all time values

        :param start_time: start time to set
        :return:
        """
