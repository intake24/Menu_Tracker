"""Download Flaming Grill's current NGCI and nutrition guides."""

from helpers import combo_PDFDownload


if __name__ == "__main__":
    combo_PDFDownload(
        "31_FlamingGrill",
        "https://www.greeneking.co.uk/pubs-restaurants-hotels/flaming-grill/ngci",
        keyword="sitecorecontenthub",
    )
