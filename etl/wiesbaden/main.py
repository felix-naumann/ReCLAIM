import os.path
import pandas as pd
from rdflib import XSD

from etl import etltools, common
from wiesbaden import preparation

EVENT_EXTRACTION_CACHE = os.path.join(
    os.path.dirname(__file__), "preparation", "event_extraction", "result_cache.json"
)

identifier_usages = {}
created_classifications = {}
created_materials = {}

authors_cache_path = os.path.join(
    os.path.dirname(__file__), "../parse_authors_column_cache.json"
)
authors_cache = etltools.JsonCache(authors_cache_path)


def create_record(row, index):
    return etltools.Record(
        source_id="wccp", collection_id="card", record_id=str(index), data=row
    )


def create_cultural_asset(
    record, image_dict, event_cache: etltools.cache.JsonCache
) -> etltools.Entity:
    identifier = record["filenameFront"]

    # Rarely filenames are used multiple times, so for subsequent uses, add an incrementing number to the identifier
    if identifier in identifier_usages:
        identifier_usages[identifier] += 1
        identifier += "_" + str(identifier_usages[identifier])
    else:
        identifier_usages[identifier] = 1

    cultural_asset = etltools.Entity(
        identifier=identifier, base_type="CulturalAsset", derived_from=record
    )

    cultural_asset.literal(
        attribute="title",
        value=common.ccp_keywords.remove_ccp_keywords(record["subject"]),
        derived_using="subject",
    )

    (weight, measurements) = preparation.weights_and_measurements.prepare(
        record["weight"], record["measurements"]
    )

    cultural_asset.literal(
        attribute="measurements",
        value=measurements,
        derived_using=["measurements", "weight"],
    )
    cultural_asset.literal(
        attribute="weight", value=weight, derived_using=["measurements", "weight"]
    )
    cultural_asset.literal(
        attribute="identifyingMarks",
        value=common.ccp_keywords.remove_ccp_keywords(record["identifyingMarks"]),
        derived_using="identifyingMarks",
    )
    cultural_asset.literal(
        attribute="physicalDescription",
        value=common.ccp_keywords.remove_ccp_keywords(record["description"]),
        derived_using="description",
    )
    cultural_asset.literal(
        attribute="wccpNumber",
        value=preparation.wccp_number.normalize(record["wccpNumber"]),
        derived_using="wccpNumber",
    )
    cultural_asset.literal(
        attribute="inventoryNumber",
        value=common.ccp_keywords.remove_ccp_keywords(record["inventoryNumber"]),
        derived_using="inventoryNumber",
    )
    cultural_asset.literal(
        attribute="catalogNumber",
        value=common.ccp_keywords.remove_ccp_keywords(record["catalogNumber"]),
        derived_using="catalogNumber",
    )
    cultural_asset.literal(
        attribute="claimNumber",
        value=common.ccp_keywords.remove_ccp_keywords(record["claimNumber"]),
        derived_using="claimNumber",
    )
    cultural_asset.literal(
        attribute="negativeNumber",
        value=common.ccp_keywords.remove_ccp_keywords(record["negativeNumber"]),
        derived_using="negativeNumber",
    )
    cultural_asset.literal(
        attribute="currentRemainDescription",
        value=common.ccp_keywords.remove_ccp_keywords(record["presumedOwner"]),
        derived_using="presumedOwner",
    )
    cultural_asset.literal(
        attribute="physicalConditionDescription",
        value=common.ccp_keywords.remove_ccp_keywords(
            record["conditionAndRepairRecord"]
        ),
        derived_using="conditionAndRepairRecord",
    )
    cultural_asset.literal(
        attribute="shelfNumber",
        value=common.ccp_keywords.remove_ccp_keywords(record["location"]),
        derived_using="location",
    )
    cultural_asset.literal(
        attribute="preConfiscationHistoryDescription",
        value=common.ccp_keywords.remove_ccp_keywords(record["presumedOwner"]),
        derived_using="presumedOwner",
    )
    cultural_asset.literal(
        attribute="informationOnImages",
        value=common.ccp_keywords.remove_ccp_keywords(record["otherPhotos"]),
        derived_using="otherPhotos",
    )
    cultural_asset.literal(
        attribute="copiesOfCard",
        value=common.ccp_keywords.remove_ccp_keywords(record["copiesOfCard"]),
        derived_using="copiesOfCard",
    )
    cultural_asset.literal(
        attribute="bibliography",
        value=common.ccp_keywords.remove_ccp_keywords(record["bibliography"]),
        derived_using="bibliography",
    )
    cultural_asset.literal(
        attribute="bundesarchivBand",
        value=common.ccp_keywords.remove_ccp_keywords(record["band"]),
        derived_using="band",
    )
    cultural_asset.literal(
        attribute="bundesarchivSignature",
        value=common.ccp_keywords.remove_ccp_keywords(record["signatur"]),
        derived_using="sigantur",
    )
    cultural_asset.literal(
        attribute="bundesarchivTitle",
        value=common.ccp_keywords.remove_ccp_keywords(record["titel"]),
        derived_using="titel",
    )
    cultural_asset.literal(
        attribute="bundesarchivStartDate",
        value=common.ccp_keywords.remove_ccp_keywords(record["vonJahr"]),
        derived_using="vonJahr",
    )
    cultural_asset.literal(
        attribute="bundesarchivEndDate",
        value=common.ccp_keywords.remove_ccp_keywords(record["bisJahr"]),
        derived_using="bisJahr",
    )
    cultural_asset.literal(
        attribute="bundesarchivPropertyCardFileNameFront",
        value=common.ccp_keywords.remove_ccp_keywords(record["filenameFront"]),
        derived_using="filenameFront",
    )
    cultural_asset.literal(
        attribute="bundesarchivPropertyCardFileNameBack",
        value=common.ccp_keywords.remove_ccp_keywords(record["filenameBack"]),
        derived_using="filenameBack",
    )

    prepare_events(cultural_asset, identifier, record, event_cache)
    prepare_post_confiscation_history(cultural_asset, record)

    relate_classifications_and_materials(cultural_asset, record, "material")
    relate_classifications_and_materials(cultural_asset, record, "classification")

    image_front = create_image(record, image_dict, "filenameFront", identifier)
    if image_front is not None:
        cultural_asset.related(
            via="referencedInCardImageFront", with_entity=image_front
        )

    image_back = create_image(record, image_dict, "filenameBack", identifier)
    if image_back is not None:
        cultural_asset.related(via="referencedInCardImageBack", with_entity=image_back)

    extract_author(record, cultural_asset, identifier)

    return cultural_asset


def prepare_events(
    cultural_asset: etltools.Entity,
    ca_id: str,
    record: etltools.Record,
    event_cache: etltools.cache.JsonCache,
):
    event_chain = preparation.history_and_ownership.get_event_chain(
        record["historyAndOwnership"],
        record["depotPossessor"],
        record["depotNumber"],
        record["arrivalCondition"],
        record["conditionAndRepairRecord"],
        record["arrivalDate"],
        record["exitDate"],
        event_cache,
    )

    if event_chain is not None:
        derived_using = [
            "historyAndOwnership",
            "depotPossessor",
            "depotNumber",
            "arrivalCondition",
            "conditionAndRepairRecord",
            "arrivalDate",
            "exitDate",
        ]
        for idx, event_data in enumerate(event_chain):
            event = common.event.create_event(
                ca_id, record, derived_using, event_data, str(idx)
            )
            cultural_asset.related(
                via="affectedCulturalAsset", with_entity=event, inverse=True
            )


def prepare_post_confiscation_history(
    cultural_asset: etltools.Entity, record: etltools.Record
):
    depot_possessor = common.ccp_keywords.remove_ccp_keywords(record["depotPossessor"])
    depot_number = common.ccp_keywords.remove_ccp_keywords(record["depotNumber"])
    history_and_ownership = common.ccp_keywords.remove_ccp_keywords(
        record["historyAndOwnership"]
    )
    derived_using = []

    depot_line_parts = []
    lines = []

    if depot_possessor is not None:
        depot_line_parts.append(depot_possessor)
        derived_using.append("depotPossessor")

    if depot_number is not None:
        depot_line_parts.append(depot_number)
        derived_using.append("depotNumber")

    if len(depot_line_parts) > 0:
        lines.append("Depot: " + ", ".join(depot_line_parts))

    if history_and_ownership is not None:
        lines.append(history_and_ownership)
        derived_using.append("historyAndOwnership")

    post_confiscation_history_description = "\n".join(lines) if len(lines) > 0 else None

    cultural_asset.literal(
        attribute="postConfiscationHistoryDescription",
        value=post_confiscation_history_description,
        derived_using=derived_using,
    )


def relate_classifications_and_materials(
    entity: etltools.Entity, record: etltools.Record, derived_from: str
) -> None:
    input_string = record[derived_from]

    if input_string is None:
        return

    (classification_uris, material_uris) = common.classification_and_material.detect(
        input_string
    )

    for classification_uri in classification_uris:
        entity.related(
            via="classifiedAs",
            with_entity_uri=classification_uri,
            derived_using=derived_from,
        )

    for material_uri in material_uris:
        entity.related(
            via="consistsOfMaterial",
            with_entity_uri=material_uri,
            derived_using=derived_from,
        )


def extract_author(record, cultural_asset, identifier) -> etltools.Entity | None:
    if record["author"] is None:
        return None

    authors_result = authors_cache.get(record["author"], None)

    if authors_result is None:
        # print(f"Author not found in cache: {record['author']}")
        return None

    if authors_result["name"] is not None or authors_result["pseudonym"] is not None:
        creator = etltools.Entity(
            identifier=identifier + "_creator", base_type="Person", derived_from=record
        )
        creator.literal(
            attribute="name",
            value=common.ccp_keywords.remove_ccp_keywords(authors_result["name"]),
            derived_using="author",
        )
        creator.literal(
            attribute="pseudonym",
            value=common.ccp_keywords.remove_ccp_keywords(authors_result["pseudonym"]),
            derived_using="author",
        )
        cultural_asset.related(via="createdBy", with_entity=creator)

    if authors_result["locationStr"] is not None:
        location = etltools.Entity(
            identifier=identifier + "_creation_location",
            base_type="Location",
            derived_from=record,
        )
        location.literal(
            attribute="description",
            value=common.ccp_keywords.remove_ccp_keywords(
                authors_result["locationStr"]
            ),
            derived_using="author",
        )
        cultural_asset.related(via="createdInLocation", with_entity=location)

    cultural_asset.literal(
        attribute="annotation",
        value=common.ccp_keywords.remove_ccp_keywords(authors_result["styleOfStr"]),
        derived_using="author",
    )
    cultural_asset.literal(
        attribute="creationDate",
        value=common.ccp_keywords.remove_ccp_keywords(authors_result["dateStr"]),
        derived_using="author",
    )


def create_image(record, imagedict, image_key, identifier) -> etltools.Entity | None:

    filename = record[image_key]
    if filename is None:
        return None

    image_name = filename + ".jpg"
    if image_name not in imagedict.keys():
        return None

    image = etltools.Entity(
        identifier=identifier + "_image_" + image_key,
        base_type="Image",
        derived_from=record,
    )

    image.literal(
        attribute="url",
        value=imagedict[image_name],
        derived_using=image_key,
        datatype=XSD.anyURI,
    )

    return image


def main():
    output_graph = etltools.create_graph("wccp")

    print("Loading WCCP source csv data..")
    data = etltools.data.csv_as_lines(
        source_id="wccp",
        file_path="wiesbaden-ccp-property-cards-ocr-export-postprocessed-16-11-23.csv",
    )

    print("Loading WCCP image csv data..")
    image_df = pd.read_csv(
        os.path.join(
            os.path.dirname(__file__), "image_upload", "imagefilenames_to_url.csv"
        )
    )
    image_dict = dict(zip(image_df["filename"], image_df[" url"]))

    event_cache = etltools.cache.JsonCache(EVENT_EXTRACTION_CACHE)

    # Create a record for each line in the csv
    records = []
    for index, line in enumerate(data):
        record = create_record(line, index)
        output_graph += record.to_graph()
        records.append(record)

    # Records -> Entities (and add them to the graph)
    print("Started parsing records to entities for the WCCP dataset!")
    for idx, record in enumerate(records):
        if idx % 500 == 0 or idx == len(records) - 1:
            print(f"Parsed {idx+1}/{len(records)} records..")

        cultural_asset = create_cultural_asset(record, image_dict, event_cache)
        output_graph += cultural_asset.to_graph()

    common.ccp_keywords.print_removed_words_wccp()

    print("Validating graph..")
    etltools.helpers.validate_graph(output_graph)

    print("Writing result to output file..")
    etltools.data.write_turtle(output_graph, "wiesbaden_output.ttl")

    # to create keyword counts for statistics
    # common.classification_and_material.write_counts("wiesbaden")


if __name__ == "__main__":
    main()
