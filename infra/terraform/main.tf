resource "hcloud_ssh_key" "admin" {
  name       = "${var.server_name}-admin"
  public_key = var.ssh_pub_key
}

resource "hcloud_firewall" "kasia" {
  name = "${var.server_name}-fw"

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "80"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "443"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "icmp"
    source_ips = ["0.0.0.0/0", "::/0"]
  }
}

resource "hcloud_server" "web" {
  name        = var.server_name
  image       = var.server_image
  server_type = var.server_type
  location    = var.server_location
  ssh_keys    = [hcloud_ssh_key.admin.id]
  user_data   = file("${path.module}/cloud-init.yaml")

  # Per context/decisions/0105-infra-security-hardening.md.
  # Hetzner daily server backups (7 rolling images, +20 % of server price).
  # NB: Hetzner deletes a server's backups together with the server — the
  # off-box copy is the manual laptop dump (infra/RUNBOOK.md § 4).
  backups = true
  # Block delete / rebuild via the API or console until explicitly unset.
  delete_protection  = true
  rebuild_protection = true

  public_net {
    ipv4_enabled = true
    ipv6_enabled = true
  }

  # user_data, ssh_keys and image are ForceNew in the hcloud provider: any
  # change to cloud-init.yaml / the admin key / the image default would
  # destroy and recreate the box — and the Postgres volume on its disk.
  # cloud-init only runs at first boot anyway, so edits to it are for the
  # next rebuild; live-box changes go through infra/RUNBOOK.md § 10.
  # To deliberately rebuild, remove this block in a reviewed PR first.
  lifecycle {
    ignore_changes = [user_data, ssh_keys, image]
  }
}

resource "hcloud_firewall_attachment" "web" {
  firewall_id = hcloud_firewall.kasia.id
  server_ids  = [hcloud_server.web.id]
}
