from typing import Final

HANGARLLM_BANNER: Final = """   ██╗  ██╗ █████╗ ███╗   ██╗ ██████╗  █████╗ ██████╗ ██╗     ██╗     ███╗   ███╗
   ██║  ██║██╔══██╗████╗  ██║██╔════╝ ██╔══██╗██╔══██╗██║     ██║     ████╗ ████║
   ███████║███████║██╔██╗ ██║██║  ███╗███████║██████╔╝██║     ██║     ██╔████╔██║
   ██╔══██║██╔══██║██║╚██╗██║██║   ██║██╔══██║██╔══██╗██║     ██║     ██║╚██╔╝██║
   ██║  ██║██║  ██║██║ ╚████║╚██████╔╝██║  ██║██║  ██║███████╗███████╗██║ ╚═╝ ██║
   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝╚═╝     ╚═╝
   One home for every AI model and agent"""

LITELLM_BANNER: Final = HANGARLLM_BANNER


def show_banner():
    try:
        import click

        click.echo(f"\n{HANGARLLM_BANNER}\n")
    except ImportError:
        print("\n")  # noqa: T201
