
def update_figure(axes, toolbar, canvas):
    for axis in axes:
        axis.clear()
        axis.grid(alpha=0.4)
    toolbar.update()
    canvas.draw_idle()


