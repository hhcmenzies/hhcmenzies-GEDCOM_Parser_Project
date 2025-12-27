from __future__ import annotations

from gedcom_parser.core.context import ParseContext
from gedcom_parser.core.exceptions import ParseExecutionError
from gedcom_parser.parser_core import GEDCOMParser
from gedcom_parser.exporter import export_registry_to_json


class Pipeline:
    """
    Orchestrates the GEDCOM parsing pipeline.
    No business logic lives here.
    """

    def __init__(self, context: ParseContext):
        self.ctx = context
        self.log = context.logger

    def run(self):
        self.log.info("Pipeline starting")

        try:
            parser = GEDCOMParser(config=self.ctx.config)
            registry = parser.run(self.ctx.input_path)

            export_registry_to_json(registry, self.ctx.output_path)

            self.log.info("Pipeline completed successfully")

            return registry

        except Exception as exc:
            self.log.exception("Pipeline execution failed")
            raise ParseExecutionError(str(exc)) from exc
