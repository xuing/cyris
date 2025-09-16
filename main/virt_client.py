# virt_client.py
import time
import libvirt
import logging

LOGGER = logging.getLogger(__name__)

class VirtClient:
    def __init__(self, uri="qemu:///session"):
        self.client = libvirt.open(uri)
        if self.client is None:
            raise RuntimeError(f"Failed to open connection to {uri}")

    def safe_lookup(self, name):
        """Return domain object if exists, otherwise None."""
        try:
            return self.client.lookupByName(name)
        except libvirt.libvirtError:
            return None

    def exists(self, name):
        """Check if domain exists."""
        return self.safe_lookup(name) is not None

    def get_state(self, name):
        """Return domain state code, or None if not found/error."""
        dom = self.safe_lookup(name)
        if not dom:
            return None
        try:
            return dom.info()[0]
        except libvirt.libvirtError:
            return None

    def shutdown_then_undefine(self, name, grace_seconds=60, destroy_on_timeout=True):
        """
        Gracefully shutdown the domain, wait for SHUTOFF, optionally force destroy if timeout,
        then undefine. Logs errors but does not raise unless libvirt is unreachable.
        """
        dom = self.safe_lookup(name)
        if not dom:
            LOGGER.debug("shutdown_then_undefine: domain '%s' not found; nothing to do.", name)
            return

        # Try graceful shutdown
        try:
            dom.shutdown()
            LOGGER.debug("shutdown_then_undefine: shutdown requested for '%s'", name)
        except libvirt.libvirtError as e:
            LOGGER.warning("shutdown_then_undefine: shutdown('%s') failed: %s", name, e)

        # Wait for shut off
        deadline = time.time() + grace_seconds
        while time.time() < deadline:
            dom2 = self.safe_lookup(name)
            if not dom2:
                LOGGER.debug("shutdown_then_undefine: domain '%s' disappeared during wait", name)
                break
            state = self.get_state(name)
            if state == libvirt.VIR_DOMAIN_SHUTOFF:
                LOGGER.debug("shutdown_then_undefine: domain '%s' is shut off", name)
                break
            time.sleep(2)
        else:
            LOGGER.warning("shutdown_then_undefine: domain '%s' did not shut off within %d seconds",
                           name, grace_seconds)
            if destroy_on_timeout:
                dom2 = self.safe_lookup(name)
                if dom2:
                    try:
                        dom2.destroy()
                        LOGGER.debug("shutdown_then_undefine: destroy called on '%s'", name)
                    except libvirt.libvirtError as e:
                        LOGGER.error("shutdown_then_undefine: destroy('%s') failed: %s", name, e)

        # Undefine domain if still exists
        dom_final = self.safe_lookup(name)
        if dom_final:
            try:
                dom_final.undefine()
                LOGGER.debug("shutdown_then_undefine: undefine succeeded for '%s'", name)
            except libvirt.libvirtError as e:
                LOGGER.error("shutdown_then_undefine: undefine('%s') failed: %s", name, e)

    def ensure_undefined(self, name, grace_seconds=60):
        """Ensure domain is fully undefined (shutdown if needed)."""
        if self.exists(name):
            self.shutdown_then_undefine(name, grace_seconds=grace_seconds)

    def list_all(self):
        """Return a list of all defined domains' names."""
        try:
            return [dom.name() for dom in self.client.listAllDomains()]
        except libvirt.libvirtError as e:
            LOGGER.error("list_all failed: %s", e)
            return []

    # ------------ launch APIs ------------
    def define_from_xml(self, xml_path) -> libvirt.virDomain|None:
        """Define a domain from an XML file. Returns domain name."""
        try:
            with open(xml_path, "r", encoding="utf-8") as f:
                xml = f.read()
        except OSError as e:
            LOGGER.error("define_from_xml: failed to read '%s': %s", xml_path, e)
        try:
            dom = self.client.defineXML(xml)
            return dom
        except libvirt.libvirtError as e:
            LOGGER.error("define_from_xml: defineXML failed: %s", e)
        return None

    @staticmethod
    def start(dom: libvirt.virDomain) -> bool:
        """Start an existing defined domain."""
        try:
            dom.create(); LOGGER.debug("start: domain '%s' started", dom.name())
            return True
        except libvirt.libvirtError as e:
            LOGGER.error("start: create('%s') failed: %s", dom.name(), e)
            return False

    def launch_from_xml(self, xml_path) -> libvirt.virDomain:
        """Define a domain from XML, then start it. Returns the domain."""
        dom = self.define_from_xml(xml_path)
        self.start(dom)
        return dom