
def update_figure(axes, toolbar, canvas):
    for axis in axes:
        axis.clear()
    toolbar.update()
    canvas.draw_idle()