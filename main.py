import fitparse
import xml.etree.ElementTree as et
from lxml import etree

# Parse the TCX file

# Modify data as needed (similarly to the example above)

# Save to a new file
if __name__ == "__main__":
    tree = etree.parse("data.tcx")
    root = tree.getroot()
    tree.write(
        "modified_data.xml", pretty_print=True, xml_declaration=True, encoding="UTF-8"
    )
    # tree = et.parse("data.tcx")
    # root = tree.getroot()
    # tree.write("modified_data.tcx")
    #
    # fitfile = fitparse.FitFile("data.fit")

    # Iterate over all messages of type "record"
    # (other types include "device_info", "file_creator", "event", etc)
    # for record in fitfile.get_messages("record"):

    # Records can contain multiple pieces of data (ex: timestamp, latitude, longitude, etc)
    # for data in record:

    # Print the name and value of the data (and the units if it has any)
    # if data.units:
    #     print(" * {}: {} ({})".format(data.name, data.value, data.units))
    # else:
    #     print(" * {}: {}".format(data.name, data.value))

    # print("---")
