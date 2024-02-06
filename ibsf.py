###########################
##### CRAWLER SECTION #####
###########################

import pycountry_convert
import country_converter

def ibsfToAlpha2CountryCode(cc: str) -> str:
    try:
        return str(country_converter.convert(names=[cc], src="IOC", to="ISO2"))
    except KeyError:
        return str(country_converter.convert(names=[cc], to="ISO2"))

def alpha2CountryCodeToContinentCode(cc: str) -> str:
    return pycountry_convert.country_alpha2_to_continent_code(cc)

from html.parser import HTMLParser
import re

htmlVoidTagSet = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"
}

def isHtmlVoidTag(tagName: str) -> bool:
    return tagName in htmlVoidTagSet

def convertToAttrDict(attrs: list[tuple[str, str | None]]) -> dict[str, str | None]:
    return dict(attrs)

def getClassName(attrs: dict[str, str | None]) -> str:
    try:
        className = attrs["class"]
    except KeyError:
        return ""
    
    if className is None:
        return ""
    return className

class IbsfAthlete:
    def __init__(self, name: str, countryCode_alpha2: str, continentCode: str) -> None:
        self.name = name
        self.countryCode_alpha2 = countryCode_alpha2
        self.continentCode = continentCode

        self.countryName = pycountry_convert.country_alpha2_to_country_name(self.countryCode_alpha2)
        self.continentName = pycountry_convert.convert_continent_code_to_continent_name(self.continentCode)
    
    def __repr__(self) -> str:
        return f"IbsfAthlete({repr(self.name)}, {repr(self.countryCode_alpha2)}, {repr(self.continentCode)})"
    
    def __str__(self) -> str:
        return f"{self.name} ({self.countryName}/{self.continentName})"

class IbsfDataSet:
    def __init__(self) -> None:
        self.athletes: list[IbsfAthlete] = []
        self.numPages: int = 0

    def addAthlete(self, name, countryCode_alpha2, continentCode) -> None:
        self.athletes.append(
            IbsfAthlete(name, countryCode_alpha2, continentCode)
        )
    
    def setNumPages(self, numPages: int) -> None:
        self.numPages = numPages

class IbsfHtmlTagHandlers:
    def __init__(self, dataset: IbsfDataSet) -> None:
        self.dataset = dataset
        self.numPages = 0

        self.isInResultBlock = False
        self.isInResultFlagBlock = False

        self.currentResultBlock_name = ""
        self.currentResultBlock_countryCode_alpha2 = ""
        self.currentResultBlock_continentCode = ""
    
    def handleStartTag(self, data: str|None, openingTagStack: list[tuple[str, dict[str, str|None]]]) -> None:
        (currentTagName, currentTagAttrs) = openingTagStack[-1]
        currentTagName = currentTagName.lower()
        if hasattr(self, f"start_{currentTagName}"):
            getattr(self, f"start_{currentTagName}")(currentTagAttrs, data, openingTagStack)
    
    def handleEndTag(self, name: str, attrs: dict[str, str|None]) -> None:
        name = name.lower()
        if hasattr(self, f"end_{name}"):
            getattr(self, f"end_{name}")(attrs)
    
    def start_a(self, attrs: dict[str, str|None], data: str|None, openingTagStack: list[tuple[str, dict[str, str|None]]]) -> None:
        className = getClassName(attrs)
        
        if "paginator--browselink" in className:
            self.numPages = max(self.numPages, int(data if data is not None else ""))
            return
        
        if "resultBlock__col" in className:
            self.isInResultBlock = True
            return
    
    def end_a(self, attrs: dict[str, str|None]) -> None:
        className = getClassName(attrs)

        if "resultBlock__col" in className:
            self.dataset.addAthlete(
                self.currentResultBlock_name,
                self.currentResultBlock_countryCode_alpha2,
                self.currentResultBlock_continentCode
            )
            self.isInResultBlock = False
            return
    
    def start_div(self, attrs: dict[str, str|None], data: str|None, openingTagStack: list[tuple[str, dict[str, str|None]]]) -> None:
        className = getClassName(attrs)

        if self.isInResultBlock and "resultBlock__flag" in className:
            self.isInResultFlagBlock = True
            return
        
        if self.isInResultBlock and "resultBlock__name" in className:
            self.currentResultBlock_name = str(data).strip()
            return

    def end_div(self, attrs: dict[str, str|None]) -> None:
        className = getClassName(attrs)

        if self.isInResultBlock and "resultBlock__flag" in className:
            self.isInResultFlagBlock = False
            return
    
    def start_img(self, attrs: dict[str, str|None], data: str|None, openingTagStack: list[tuple[str, dict[str, str|None]]]) -> None:
        className = getClassName(attrs)

        if self.isInResultFlagBlock and "flag" in className:
            try:
                imgSrc = attrs["src"]
                if not imgSrc: raise KeyError
            except KeyError:
                raise RuntimeError("Flag image has no source")
            
            m = re.match(r"\/fileadmin\/Images\/Icons\/Flags\/[^/]+\/(?P<country_code>[A-Z]{3}).png", imgSrc)
            try:
                if not m: raise TypeError
                countryCode_alpha3 = m.group("country_code")
                if not countryCode_alpha3: raise ValueError
            except:
                raise RuntimeError(f"Could not extract country code from flag image source: {imgSrc}")
            countryCode_alpha2 = ibsfToAlpha2CountryCode(countryCode_alpha3)
            continentCode = alpha2CountryCodeToContinentCode(countryCode_alpha2)

            self.currentResultBlock_countryCode_alpha2 = countryCode_alpha2
            self.currentResultBlock_continentCode = continentCode
    
    def end_html(self, attrs: dict[str, str|None]) -> None:
        self.dataset.setNumPages(self.numPages)

class IbsfHtmlParser(HTMLParser):
    def __init__(self, dataset: IbsfDataSet, convert_charrefs: bool = True) -> None:
        super().__init__(convert_charrefs=convert_charrefs)
        self.dataset = dataset
        self.tagHandlers = IbsfHtmlTagHandlers(dataset)

        self.openingTagStack: list[tuple[str, dict[str, str|None]]] = []
        self.lastTagHasData = False
    
    def handle_starttag(self, tagName: str, attrs: list[tuple[str, str | None]]) -> None:
        self.openingTagStack.append(
            (tagName, convertToAttrDict(attrs))
        )
        self.lastTagHasData = False
        if isHtmlVoidTag(tagName):
            self.handle_endtag(tagName)
    
    def handle_endtag(self, tagName: str) -> None:
        if not self.lastTagHasData:
            self.tagHandlers.handleStartTag(None, self.openingTagStack)
        for i in range(len(self.openingTagStack) - 1, -1, -1):
            (endTagName, endTagAttrs) = self.openingTagStack[i]
            if endTagName == tagName:
                del self.openingTagStack[i]
                self.tagHandlers.handleEndTag(endTagName, endTagAttrs)
                break
    
    def handle_data(self, data: str) -> None:
        if not self.openingTagStack:
            if re.match(r"\s*", data): return
            raise Exception(f"handle_data called when no tag is open. Data: '''{data}'''")
        self.tagHandlers.handleStartTag(data, self.openingTagStack)
        self.lastTagHasData = True

import requests

def crawlOnePage(dataset: IbsfDataSet, pageNumber: int):
    print(f"Parsing page {pageNumber}/{dataset.numPages if dataset.numPages > 0 else "<unknown>"}... ", end='', flush=True)
    parser = IbsfHtmlParser(dataset)
    url = f"https://www.ibsf.org/en/athletes?tx_fmathletes_list%5Bgender%5D=&tx_fmathletes_list%5Bnation%5D=&tx_fmathletes_list%5Bpage%5D={pageNumber}&tx_fmathletes_list%5Bseason%5D=1000004&tx_fmathletes_list%5Bsport%5D=&tx_fmathletes_list%5Bsword%5D"
    r = requests.get(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    })
    parser.feed(r.text)
    print("Done", flush=True)

def crawl(dataset: IbsfDataSet):
    crawlOnePage(dataset, 1)
    pageNumber = 2
    while pageNumber <= dataset.numPages:
        crawlOnePage(dataset, pageNumber)
        pageNumber += 1

###################################
##### EXCEL EXPORTING SECTION #####
###################################

import pandas as pd

def writeToExcel(writer: pd.ExcelWriter, dataset: IbsfDataSet):
    athletesInContinents: dict[str, list[IbsfAthlete]] = {}

    for a in dataset.athletes:
        try:
            athletesInContinents[a.continentName].append(a)
        except KeyError:
            athletesInContinents[a.continentName] = [a]
    
    for continentName, athletesInContinent in athletesInContinents.items():
        athletesInContinent.sort(key=lambda a: a.name)
        data = {
            "Athlete Name": map(lambda a: a.name, athletesInContinent),
            "Country": map(lambda a: a.countryName, athletesInContinent),
            "Continent": continentName
        }
        df = pd.DataFrame(data)
        df.index += 1
        df.to_excel(writer, sheet_name=continentName, index=True)

import os
from pathvalidate import is_valid_filepath

def exportExcel(dataset: IbsfDataSet) -> None:
    print("Processing... ", end='', flush=True)
    print("Done")

    fileName = ""
    try:
        fileNameEnteredOnce = False
        while True:
            prompt = "Enter Excel file name (empty to abort): " if not fileNameEnteredOnce else "Re-enter Excel file name (empty to abort): "
            fileName = input(prompt)
            fileNameEnteredOnce = True
            if not fileName: raise KeyboardInterrupt
            if not fileName.endswith(".xls") and not fileName.endswith(".xlsx"):
                fileName += ".xlsx"
            fileName = os.path.abspath(fileName)
            if not is_valid_filepath(fileName, platform="auto"):
                print(f"ERROR: Invalid file name: {fileName}")
                continue # re-enter
            if os.path.isfile(fileName):
                try:
                    input("This file already exists. Press ENTER to overwrite it ; Ctrl-C if you don't want to.")
                except KeyboardInterrupt:
                    print("")
                    continue # re-enter
            if os.path.isdir(fileName):
                print("ERROR: This is a directory !")
                continue # re-enter

            print(f"Writing to: {fileName}")
            try:
                with pd.ExcelWriter(fileName) as writer:
                    writeToExcel(writer, dataset)
                break
            except Exception as e:
                print(f"ERROR: {e}. Please try again.")
    except KeyboardInterrupt:
        print("\nOperation cancelled. Nothing is exported.")
        return

    print("Done")

def main():
    dataset = IbsfDataSet()
    crawl(dataset)
    print(f"COMPLETE. Total number of athletes: {len(dataset.athletes)}.")
    exportExcel(dataset)

main()
