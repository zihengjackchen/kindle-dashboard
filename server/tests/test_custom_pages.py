import pytest
from pydantic import ValidationError
from app.layout import Layout, Widget
from app.snapshots import Snapshot
from app.main import create_app
from app.config import Settings
from fastapi.testclient import TestClient


def test_legacy_usage_is_discarded_without_losing_weather_or_layout():
    layout=Layout.model_validate({'widgets':[{'id':'weather'},{'id':'chatgpt'}], 'tickers':['AAPL']})
    assert [w.id for w in layout.widgets]==['weather'] and layout.tickers==['AAPL']
    assert 'chatgpt' not in Snapshot.model_validate({'chatgpt':{'private':'ignored'}}).model_dump()


@pytest.mark.parametrize('value',[
    {'widgets':[{'id':'nas','fields':['password']}]},
    {'widgets':[{'id':'weather','fields':['temperature','temperature']}]},
    {'page_order':['nas','nas']},{'refresh_minutes':0},{'pages':{'../../private':{}}},
])
def test_invalid_custom_configuration(value):
    with pytest.raises(ValidationError): Layout.model_validate(value)


def test_page_settings_and_client_contract(tmp_path):
    client=TestClient(create_app(Settings(api_token='test',layout_path=str(tmp_path/'layout.json'))))
    auth={'Authorization':'Bearer test'}
    assert client.get('/client-config.json').status_code==401
    result=client.put('/layout',headers=auth,json={'page_order':['overview','nas'],'refresh_minutes':15,
        'pages':{'nas':{'title':'My server','widgets':[{'id':'nas','fields':['uptime','cpu_percent']}]}}})
    assert result.status_code==200
    config=client.get('/client-config.json',headers=auth)
    assert config.headers['cache-control']=='no-store'
    assert config.json()['pages']==[{'id':'overview','name':'Dashboard'},{'id':'nas','name':'My server'}]
    assert config.json()['refresh_minutes']==15
    assert client.get('/dashboard.png?page=nas',headers=auth).status_code==200
