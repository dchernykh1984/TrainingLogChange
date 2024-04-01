from datetime import datetime
from functools import lru_cache

from lxml import etree


def parse_date(date_string: str) -> datetime:
    return datetime.strptime(date_string.strip(), "%Y-%m-%dT%H:%M:%S.%fZ")


def dump_date(date: datetime) -> str:
    return date.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class TCXModifier:
    FIELD_PARSER = {
        "Speed": (float, str),
        "TotalTimeSeconds": (float, str),
        "MaximumSpeed": (float, str),
        "Time": (parse_date, dump_date),
        "StartTime": (parse_date, dump_date),
    }

    def __init__(self, file_path: str):
        self.tree = etree.parse(file_path)
        self.root = self.tree.getroot()

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

    @lru_cache
    def _get_start_time(self):
        time_tag = "}Time"
        return min(
            [
                parse_date(element.text)
                for element in self.root.iter()
                if element.tag.endswith(time_tag)
            ]
        )

    def speedup(self, multiplier: float) -> None:
        """
        Method modifies tcx data: TotalTimeSeconds, MaximumSpeed, Speed, Time, StartTime
        :param multiplier: value to speedup. i.e. 1.1 means, 10% speedup
        :return:
        """
        start_time = self._get_start_time()
        multiply = {
            "Speed",
            "MaximumSpeed",
        }
        divide = {
            "TotalTimeSeconds",
        }
        time_fields = {"Time", "StartTime"}
        for element in self.root.iter():
            tag: str = element.tag.split("}")[-1]
            if tag in self.FIELD_PARSER:
                element_data = self.FIELD_PARSER.get(tag)[0](element.text)
                if tag in multiply:
                    element_data = element_data * multiplier
                elif tag in divide:
                    element_data = element_data / multiplier
                elif tag in time_fields:
                    element_data = start_time + (element_data - start_time) / multiplier
                else:
                    continue
                element.text = self.FIELD_PARSER.get(tag)[1](element_data)

    def cleanup_heart_rate(self, max_hr: int) -> None:
        """
                <MaximumHeartRateBpm>
          <Value>230</Value>
        </MaximumHeartRateBpm>
                    <HeartRateBpm>
              <Value>99</Value>
            </HeartRateBpm>

        :param max_hr:
        :return:
        """
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

    def update_start_time(self, update_time: str) -> None:
        """
        Set start time and move all time values

        :param update_time: start time to set, i.e. '2024-03-31T23:53:51.000Z'
        :return:
        """
        start_time = self._get_start_time()
        time_fields = {
            "Time",
        }
        for element in self.root.iter():
            tag: str = element.tag.split("}")[-1]
            if tag in self.FIELD_PARSER and tag in time_fields:
                element_data = self.FIELD_PARSER.get(tag)[0](element.text)
                element_data = parse_date(update_time) + (element_data - start_time)
                element.text = self.FIELD_PARSER.get(tag)[1](element_data)
            if tag == "Lap":
                element.attrib["StartTime"] = update_time

    def print_field(self, field_name: str) -> None:
        for element in self.root.iter():
            if field_name in element.tag:
                print(
                    f"aTag: {element.tag}, Text: {element.text.strip() if element.text else 'N/A'}, Attributes: {element.attrib}"
                )
