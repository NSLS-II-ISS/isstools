
def update_figure(axes, toolbar, canvas):
    for axis in axes:
        axis.clear()

    toolbar.update()
    canvas.draw_idle()
    axes[-1].grid(alpha=0.4)


