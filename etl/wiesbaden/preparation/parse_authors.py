from etl import etltools, common

if __name__ == "__main__":
    df = etltools.data.csv_as_dataframe(
        source_id="wccp",
        file_path="wiesbaden-ccp-property-cards-ocr-export-postprocessed-16-11-23.csv",
    )

    df.loc[df["author"] == "Unknown", "author"] = None
    df.loc[df["author"] == "unknown", "author"] = None
    df.loc[df["author"] == "Various", "author"] = None
    df.loc[df["author"] == "various", "author"] = None
    df.loc[df["author"] == "modern", "author"] = None

    df = df[["author"]].dropna().drop_duplicates()

    cache = etltools.JsonCache("../../parse_authors_column_cache.json")
    df = common.authors.parse_author_column_using_openai(df, cache)
