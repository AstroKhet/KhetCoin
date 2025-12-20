

# UI_GREEN = 
# UI_RED = 


KHET_ORANGE_LIGHT = "#FFE5C0"



BTN_STOP_RED = "#dc3545"
BTN_START_GREEN = "#28a745"
BTN_CONFIG_GRAY = "#6e7f80"
BTN_NEUTRAL_BLUE = "#9dbcd4"

# Generator for alternative colorings

def colour_pattern_gen(colours):
    n = len(colours)
    i = 0
    while True:
        yield colours[i % n]
        i += 1
        