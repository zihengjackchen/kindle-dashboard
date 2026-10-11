from io import BytesIO
import pytest
from PIL import Image
from pydantic import ValidationError
from app.layout import Layout, Widget
from app.widgets import widget_slots
from app.markdown_widget import markdown_image, blocks
from app.renderer import render_dashboard
from app.config import Settings
from app.models import DashboardRequest


def test_repeated_widgets_and_reserved_positions():
    layout=Layout(widgets=[Widget(id="nas",key="cpu",fields=["cpu_percent"],row=1,column=2),
                           Widget(id="nas",key="storage",fields=["pool_health"]),
                           Widget(id="markdown",key="text",row=2,width="full",content="# Today")])
    rows=widget_slots(layout.widgets)
    assert {(w.key,col,span) for w,col,span in rows[0]} == {("cpu",1,1),("storage",0,1)}
    assert rows[1][0][0].key == "text" and rows[1][0][2] == 2
    with pytest.raises(ValidationError):
        Layout(widgets=[Widget(id="nas",key="one",row=1),Widget(id="weather",key="two",row=1)])
    with pytest.raises(ValidationError):
        Widget(id="markdown",row=2,column=2,width="full")
    with pytest.raises(ValidationError):
        Layout(widgets=[Widget(id="nas",key="same"),Widget(id="weather",key="same")])


def test_markdown_fits_and_truncates_without_drawing_outside_box():
    image,truncated=markdown_image("# Today\n- **Read** a book\n[Calendar](https://invalid.test)\n`task`",450,300)
    assert image.mode=="L" and image.size==(450,300) and not truncated
    assert image.getextrema()[0]==0
    for overflow in ("shrink","truncate"):
        image,truncated=markdown_image("Very long words and notes.\n"*100,150,80,overflow=overflow)
        assert image.size==(150,80) and truncated
    _,shrunk=markdown_image("One line\nTwo lines\nThree lines",250,83,overflow="shrink")
    _,clipped=markdown_image("One line\nTwo lines\nThree lines",250,83,overflow="truncate")
    assert not shrunk and clipped


def test_markdown_link_and_image_labels_never_fetch_resources():
    assert list(blocks("![Local](file:///etc/passwd) [Remote](http://127.0.0.1/)"))[0][0]=="Local Remote"
    image,_=markdown_image("<script>plain text</script>\n```\n"+'x'*4000,200,100)
    assert image.size==(200,100)


@pytest.mark.parametrize("width,height",[(600,800),(1056,1162),(1648,1236)])
def test_independent_content_and_markdown_render_at_device_resolutions(width,height):
    layout=Layout(widgets=[Widget(id="markdown",key="one",content="# Morning\n- **Coffee**\n- Plan the day"),
                           Widget(id="markdown",key="two",content="## Evening\n> Read a book",overflow="truncate"),
                           Widget(id="markets",tickers=["VOO"],width="full")])
    png=render_dashboard(DashboardRequest(width=width,height=height),Settings(),layout=layout)
    image=Image.open(BytesIO(png));image.load()
    assert image.size==(width,height) and image.mode=="L"


def test_bounded_widget_content_and_tickers():
    for kwargs in ({"content":"x"*4001},{"tickers":["UNKNOWN"]},{"tickers":["VOO","VOO"]},
                   {"notes":["x"*101]},{"row":13}):
        with pytest.raises(ValidationError):
            Widget(id="markdown",**kwargs)
