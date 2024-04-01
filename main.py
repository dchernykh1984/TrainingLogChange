from tcx_modifier import TCXModifier

if __name__ == "__main__":
    modifier = TCXModifier("data.tcx")
    modifier.cleanup_power(2000.0)
    modifier.cleanup_canence(200)
    modifier.cleanup_heart_rate(200)
    modifier.speedup(1.5)
    modifier.save("modified_data.xml")
