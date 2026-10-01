# DeepWiki and Ask Devin on this repo (demo guide)

- **DeepWiki** indexes a connected repo and generates a browsable wiki with architecture
  diagrams, summaries and links to source. Docs: https://docs.devin.ai/work-with-devin/deepwiki
- **Ask Devin** answers questions about the code, grounded in the index and the wiki, with
  citations, and can start a session from the conversation. Docs:
  https://docs.devin.ai/work-with-devin/ask-devin

Demo flow: open the wiki for `cogdeasy/cogdeasy-gsk-abap2xlsx`, show the writer/reader
architecture page, then ask the questions below in Ask Devin and compare the cited files with the
answers here. Each answer was checked against the code in this repo.

## 1. Which classes write the XLSX package?

`ZCL_EXCEL_WRITER_2007` implements `zif_excel_writer` (`src/zcl_excel_writer_2007.clas.abap:9`).
`zif_excel_writer~write_file` (line 6546) calls `create` (line 323), which builds each part with
a `create_*` method, adds it to a `cl_abap_zip` archive and returns `lo_zip->save( )` (line 592).
`ZCL_EXCEL_WRITER_XLSM` and `ZCL_EXCEL_WRITER_HUGE_FILE` inherit from it; `ZCL_EXCEL_WRITER_CSV`
implements the same interface but writes CSV.

## 2. Where are cell styles mapped to the indexes in styles.xml?

`ZCL_EXCEL_WRITER_2007->create_xl_styles` (`src/zcl_excel_writer_2007.clas.abap:4534`) loops
over `excel->get_styles_iterator( )` (line 4722), de-duplicates into `cellXfs` and fills
`styles_mapping` (style GUID to 0-based index, lines 4846-4856). Sheet writing reads that table to
set each cell's `s` attribute (lines 4460-4465). On the model side, `ZCL_EXCEL->add_new_style`
(`src/zcl_excel.clas.abap:230`) keeps `t_stylemapping1/2`.

## 3. How does the reader load a file?

`zif_excel_reader~load_file` (`src/zcl_excel_reader_2007.clas.abap:4451`) reads bytes with
`read_from_applserver` (line 4080, `OPEN DATASET`) or `read_from_local_file` (line 4120,
`cl_gui_frontend_services=>gui_upload`), then calls `zif_excel_reader~load` (line 4357). That
parses the package via `load_workbook` (1788), `load_styles` (1045) and `load_shared_strings` (904).

## 4. How does the huge-file writer differ from the standard writer?

`ZCL_EXCEL_WRITER_HUGE_FILE` inherits from `ZCL_EXCEL_WRITER_2007`
(`src/zcl_excel_writer_huge_file.clas.abap:3`) and redefines only `create_xl_sharedstrings`
(line 41) and `create_xl_sheet` (line 118). Both render XML with custom simple transformations,
`zexcel_tr_shared_strings` (line 108) and `zexcel_tr_sheet` (line 750), instead of iXML DOM.

## 5. What is in `src/not_cloud/` and why?

The package text is "Objects which cannot work in SAP Cloud" (`src/not_cloud/package.devc.xml`):
the ALV/SALV converters, `ZCL_EXCEL_OLE` and the program `ZEXCEL_TEMPLATE_GET_TYPES`, 11 non-DDIC
objects in total. `abaplint-steampunk.json:4` sets `"noIssues": ["/demos/", "/not_cloud/"]`, so
the ABAP Cloud lint ignores this folder.

## 6. Does code outside `not_cloud/` depend on SAP GUI?

Yes, in two places. `read_from_local_file` uses `cl_gui_frontend_services=>gui_upload`
(`src/zcl_excel_reader_2007.clas.abap:4129`). `ZCL_EXCEL_WORKSHEET->bind_alv_ole2` takes a
`cl_gui_alv_grid` parameter (`src/zcl_excel_worksheet.clas.abap:148-153`) and calls
`ZCL_EXCEL_OLE` dynamically (line 947). See `docs/s4/remediation-plan.md`, wave 3.
