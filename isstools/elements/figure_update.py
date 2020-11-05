
def update_figure(axes, toolbar, canvas):
    for axis in axes:
        axis.clear()

    toolbar.update()
    canvas.draw_idle()
    axes[-1].grid(alpha=0.4)


def update_figure_with_colorbar(axes, toolbar, canvas,figure):
    if len(figure.axes) >1:
        figure.axes[-1].remove()
    for axis in axes:
        axis.clear()

    toolbar.update()
    canvas.draw_idle()
    axes[-1].grid(alpha=0.4)



