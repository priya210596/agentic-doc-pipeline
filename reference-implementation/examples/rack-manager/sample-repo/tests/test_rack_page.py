# RACK-210: covers the Ports and Cabling tabs
def test_tab_labels():
    assert tab_labels() == ["Ports", "Cabling"]
