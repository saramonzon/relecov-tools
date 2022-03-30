#!/usr/bin/env python
import os
import logging

# from rich.prompt import Confirm
import click
import rich.console
import rich.logging
import rich.traceback

import relecov_tools.utils
import relecov_tools.read_metadata
import relecov_tools.sftp_handle
import relecov_tools.ena_upload
import relecov_tools.json_validation
import relecov_tools.map_schema

log = logging.getLogger()


def run_relecov_tools():

    # Set up rich stderr console
    stderr = rich.console.Console(
        stderr=True, force_terminal=relecov_tools.utils.rich_force_colors()
    )

    # Set up the rich traceback
    rich.traceback.install(console=stderr, width=200, word_wrap=True, extra_lines=1)

    # Print nf-core header
    # stderr.print("\n[green]{},--.[grey39]/[green],-.".format(" " * 42), highlight=False)
    stderr.print(
        "[blue]                ___   ___       ___  ___  ___                           ",
        highlight=False,
    )
    stderr.print(
        "[blue]   \    |-[grey39]-|  [blue] |   \ |    |    |    |    |   | \      /  ",
        highlight=False,
    )
    stderr.print(
        "[blue]    \   \  [grey39]/ [blue]  |__ / |__  |    |___ |    |   |  \    /   ",
        highlight=False,
    )
    stderr.print(
        "[blue]    /  [grey39] / [blue] \   |  \  |    |    |    |    |   |   \  /    ",
        highlight=False,
    )
    stderr.print(
        "[blue]   /   [grey39] |-[blue]-|   |   \ |___ |___ |___ |___ |___|    \/     ",
        highlight=False,
    )

    # stderr.print("[green]                                          `._,._,'\n", highlight=False)
    __version__ = "0.0.1"
    stderr.print(
        "[grey39]    RELECOV-tools version {}".format(__version__), highlight=False
    )

    # Lanch the click cli
    relecov_tools_cli()


# Customise the order of subcommands for --help
class CustomHelpOrder(click.Group):
    def __init__(self, *args, **kwargs):
        self.help_priorities = {}
        super(CustomHelpOrder, self).__init__(*args, **kwargs)

    def get_help(self, ctx):
        self.list_commands = self.list_commands_for_help
        return super(CustomHelpOrder, self).get_help(ctx)

    def list_commands_for_help(self, ctx):
        """reorder the list of commands when listing the help"""
        commands = super(CustomHelpOrder, self).list_commands(ctx)
        return (
            c[1]
            for c in sorted(
                (self.help_priorities.get(command, 1000), command)
                for command in commands
            )
        )

    def command(self, *args, **kwargs):
        """Behaves the same as `click.Group.command()` except capture
        a priority for listing command names in help.
        """
        help_priority = kwargs.pop("help_priority", 1000)
        help_priorities = self.help_priorities

        def decorator(f):
            cmd = super(CustomHelpOrder, self).command(*args, **kwargs)(f)
            help_priorities[cmd.name] = help_priority
            return cmd

        return decorator


@click.group(cls=CustomHelpOrder)
@click.version_option(relecov_tools.__version__)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Print verbose output to the console.",
)
@click.option(
    "-l", "--log-file", help="Save a verbose log to a file.", metavar="<filename>"
)
def relecov_tools_cli(verbose, log_file):

    # Set the base logger to output DEBUG
    log.setLevel(logging.DEBUG)

    # Set up logs to a file if we asked for one
    if log_file:
        log_fh = logging.FileHandler(log_file, encoding="utf-8")
        log_fh.setLevel(logging.DEBUG)
        log_fh.setFormatter(
            logging.Formatter(
                "[%(asctime)s] %(name)-20s [%(levelname)-7s]  %(message)s"
            )
        )
        log.addHandler(log_fh)


# @relecov_tools_cli.command(help_priority=1)
# @click.argument("keywords", required=False, nargs=-1, metavar="<filter keywords>")
# @click.option(
#    "-s",
#    "--sort",
#    type=click.Choice(["release", "pulled", "name", "stars"]),
#    default="release",
#    help="How to sort listed pipelines",
# )
# @click.option("--json", is_flag=True, default=False, help="Print full output as JSON")
# @click.option(
#    "--show-archived", is_flag=True, default=False, help="Print archived workflows"
# )
# def list(keywords, sort, json, show_archived):
#    """
#    List available bu-isciii workflows used for relecov.
#    Checks the web for a list of nf-core pipelines with their latest releases.
#    Shows which nf-core pipelines you have pulled locally and whether they are up to date.
#    """
#    pass


# sftp
@relecov_tools_cli.command(help_priority=2)
@click.option("-u", "--user", help="User name for login to sftp server")
@click.option("-p", "--password", help="password for the user to login")
@click.option(
    "-f",
    "--conf_file",
    help="Configuration file (no params file)",
)
def download(user, password, conf_file):
    """Download files located in sftp server."""
    sftp_connection = relecov_tools.sftp_handle.SftpHandle(user, password, conf_file)
    sftp_connection.download()


# metadata
@relecov_tools_cli.command(help_priority=3)
@click.option(
    "-m",
    "--metadata_file",
    type=click.Path(),
    help="file containing metadata",
)
@click.option(
    "-s",
    "--sample_list_file",
    type=click.Path(),
    default=os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "assets",
        "additional_metadata.json",
    ),
    help="Json with the additional metadata to add to the received user metadata",
)
@click.option(
    "-o", "--metadata-out", type=click.Path(), help="Path to save output  metadata file"
)
def read_metadata(metadata_file, sample_list_file, metadata_out):
    """
    Create the json compliant to the relecov schema from the Metadata file.
    """
    new_metadata = relecov_tools.read_metadata.RelecovMetadata(
        metadata_file, sample_list_file, metadata_out
    )
    relecov_json = new_metadata.create_metadata_json()
    return relecov_json


# validation
@relecov_tools_cli.command(help_priority=4)
@click.option("-j", "--json_file", help="Json file to validate")
@click.option("-s", "--json_schema", help="Json schema")
@click.option("-o", "--out_folder", help="Path to save validate json file")
def validate(json_file, json_schema, out_folder):
    """Validate json file against schema."""
    (
        validated_json_data,
        invalid_json,
        errors,
    ) = relecov_tools.json_validation.validate_json(json_file, json_schema, out_folder)
    if len(invalid_json) > 0:
        log.error("Some of the samples in json metadata were not validated")
    else:
        log.info("All data in json were validated")


# mapping to ENA schema
@relecov_tools_cli.command(help_priority=5)
@click.option("-p", "--origin_schema", help="File with the origin (relecov) schema")
@click.option("-j", "--json_data", help="File with the json data to convert")
@click.option(
    "-d",
    "--destination_schema",
    type=click.Choice(["ENA", "GSAID", "other"], case_sensitive=True),
    help="schema to be mapped",
)
@click.option("-f", "--schema_file", help="file with the custom schema")
@click.option("-o", "--output", help="File name and path to store the mapped json")
def map(phage_plus_schema, json_data, destination_schema, schema_file, output):
    """Convert data between phage plus schema to ENA, GISAID, or any other schema"""
    new_schema = relecov_tools.conversion_schema.MappingSchema(
        origin_schema, json_data, destination_schema, schema_file, output
    )
    new_schema.map_to_data_to_new_schema()


@relecov_tools_cli.command(help_priority=6)
@click.option("-u", "--user", help="user name for login to ena")
@click.option("-p", "--password", help="password for the user to login")
@click.option("-e", "--ena_json", help="where the validated json is")
@click.option("-s", "--study", help="study/project name to include in xml files")
@click.option(
    "-a",
    "--action",
    type=click.Choice(["add", "modify", "cancel", "release"], case_sensitive=False),
    help="select one of the available options",
)
@click.option("--dev/--production", default=True)
@click.option("-o", "--output_path", help="output folder for the xml generated files")
def upload_to_ena(user, password, ena_json, dev, study, action, output_path):
    """parsed data to create xml files to upload to ena"""
    upload_ena = relecov_tools.ena_upload.upload(
        user, password, ena_json, dev, study, action, output_path
    )
    upload_ena.upload_files_to_ena()


@relecov_tools_cli.command(help_priority=7)
@click.option("-u", "--user", help="user name for login")
@click.option("-p", "--password", help="password for the user to login")
@click.option("-e", "--gisaid_json", help="where the validated json is")
@click.option("-o", "--output_path", help="output folder for the xml generated files")
def upload_to_gisaid(user, password, gisaid_json, output_path):
    """parsed data to create files to upload to gisaid"""
    pass


@relecov_tools_cli.command(help_priority=8)
@click.option("-u", "--user", help="user name for connecting to the server")
def launch(user):
    """launch viralrecon in hpc"""
    pass


@relecov_tools_cli.command(help_priority=9)
@click.option("-j", "--json", help="data in json format")
def update_db(user):
    """feed database with metadata jsons"""
    pass


if __name__ == "__main__":
    run_relecov_tools()
