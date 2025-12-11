

# UI_GREEN = 
# UI_RED = 


KHET_ORANGE_LIGHT = "#FFE5C0"




# Generator for alternative colorings

def colour_pattern_gen(colours):
    n = len(colours)
    i = 0
    while True:
        yield colours[i % n]
        i += 1
        