from tcx_modifier import TCXModifier


if __name__ == "__main__":
    modifier = TCXModifier("data.tcx")
    modifier.cleanup_power(2000.0)
    modifier.cleanup_canence(200)
    modifier.cleanup_heart_rate(200)
    modifier.speedup(1.8)
    modifier.update_start_time("2024-03-31T15:53:51.000Z")
    modifier.print_field("Lap")
    modifier.save("modified_data.tcx")
