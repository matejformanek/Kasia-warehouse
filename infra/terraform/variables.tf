variable "hcloud_token" {
  description = "Hetzner Cloud API token. Read from HCLOUD_TOKEN env var (TF_VAR_hcloud_token)."
  type        = string
  sensitive   = true
}

variable "ssh_pub_key" {
  description = "Public SSH key registered with the server for first-boot login."
  type        = string
}

variable "admin_ip" {
  description = "IPv4 of Matej's workstation in CIDR form (e.g. 192.0.2.5/32). SSH is firewalled to this address only."
  type        = string
}

variable "server_name" {
  description = "Hetzner server name."
  type        = string
  default     = "kasia-prod"
}

variable "server_type" {
  description = "Hetzner server type. CPX22: 3 vCPU AMD EPYC, 8 GB, 80 GB NVMe."
  type        = string
  default     = "cpx22"
}

variable "server_location" {
  description = "Hetzner datacentre. fsn1 = Falkenstein, DE."
  type        = string
  default     = "fsn1"
}

variable "server_image" {
  description = "OS image. Pinned to a current Ubuntu LTS at apply time."
  type        = string
  default     = "ubuntu-24.04"
}
