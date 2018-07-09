
def reset_plot(axes = [], toolbar = None, canvas = None):
    if axes:
        for axis in axes:
            print('aaaa')
            axis.clear()
    if toolbar is not None:
        print('nnn')
        toolbar.update()
    if canvas is not None:
        print('ggg')
        canvas.draw_idle()
