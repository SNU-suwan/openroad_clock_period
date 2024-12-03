import os
import sys
import argparse
import subprocess

import utils

DESIGN_DIR = None
FLOW_DIR = None
RESULTS_DIR = None

STAGE_TO_EXTRACT_WORST_SLACK = "5_route"

def get_args():
	parser = argparse.ArgumentParser(description='Identify clock period', formatter_class=argparse.ArgumentDefaultsHelpFormatter)

	parser.add_argument('-d', help = 'design', dest = 'design', default = 'gcd')
	parser.add_argument('-p', help = 'platform', dest = 'platform', default = 'nangate45')

	parser.add_argument('-u', help = 'initial utilization', dest = 'utilization', default = None) # Set None to skip modification of utilization.
	parser.add_argument('-c', help = 'initial clock period (ps)', dest = 'clock_period', default = 300, type = float)

	# Aim at finding clock_period satisfying: lower_bound * clock_period <= worst slack <= upper_bound * clock_period
	parser.add_argument('-lb', help = 'lower bound', dest = 'lower_bound', default = -0.5, type = float) 
	parser.add_argument('-ub', help = 'upper bound', dest = 'upper_bound', default = 0.5, type = float)

	parser.add_argument('-openroad_dir', help = 'openroad flow script directory', dest = 'openroad_dir', default = '/root/OpenROAD-flow-scripts')
	return parser.parse_args()


def modify_config(args):
	'''
    Modify config.mk to set CORE_UTILIZATION to the value of args.utilization.
    If args.utilization is set to None, then this function will not execute.
    If there is no CORE_UTILIZATION defined in config.mk, this function will result in an error.
	'''
	global DESIGN_DIR, FLOW_DIR
	config_dir = os.path.join(DESIGN_DIR, 'config.mk')
	tmp_dir = os.path.join(DESIGN_DIR, 'tmp.mk')
	
	if os.path.isfile(config_dir):
		is_modified = False
		with open(config_dir, 'r') as original_file:
			with open(tmp_dir, 'w') as tmp_file:
				lines = original_file.readlines()
				util_found = False
				util_param_found = False
				for line in lines:
					if line.startswith("export CORE_UTILIZATION") and args.utilization is not None:
						if not line.startswith(f'export CORE_UTILIZATION = {args.utilization}'):
							tmp_file.write(f'# {line}')
							tmp_file.write(f'export CORE_UTILIZATION = {args.utilization}\n')
							util_found = True
							is_modified = True
						else:
							tmp_file.write(line)
						util_param_found = True
					elif line.startswith("export FLOORPLAN_DEF") or line.startswith("export CORE_AREA") or line.startswith("export DIE_AREA"):
						tmp_file.write(line)
						util_param_found = True
					elif line.startswith("export VERILOG_FILES"):
						if not line.startswith(f'export VERILOG_FILES          = $(sort $(wildcard {FLOW_DIR}/designs/src/$(DESIGN_NAME)/*.v))\n'):
							tmp_file.write(f'# {line}')
							tmp_file.write(f'export VERILOG_FILES          = $(sort $(wildcard {FLOW_DIR}/designs/src/$(DESIGN_NAME)/*.v))\n')
							is_modified = True
						else:
							tmp_file.write(line)
					elif line.startswith("export SDC_FILE"):
						if not line.startswith(f'export SDC_FILE               = {FLOW_DIR}/designs/$(PLATFORM)/$(DESIGN_NAME)/constraint.sdc\n'):
							tmp_file.write(f'# {line}')
							tmp_file.write(f'export SDC_FILE               = {FLOW_DIR}/designs/$(PLATFORM)/$(DESIGN_NAME)/constraint.sdc\n')
							is_modified = True
						else:
							tmp_file.write(line)
					else:
						tmp_file.write(line)

				if not util_param_found:
					if args.utilization is None:
						print("[ERROR] Floorplan information is not given in config.mk nor as an argument.")
						assert False
					tmp_file.write(f'export CORE_UTILIZATION = {args.utilization}\n')
					is_modified = True
		if is_modified:
			utils.create_backups(config_dir)
			os.system(f'mv {tmp_dir} {config_dir}')
			print(f"Config file, {config_dir}, has modified.")
		else:
			os.system(f'rm {tmp_dir}')

		if not util_found and args.utilization is not None:
			print(f"[ERROR] Config file, {config_dir}, does not include CORE_UTILIZATION.")
			print(" Utilization cannot be changed.")
			#sys.exit(-1)
			assert False
	else:
		print(f"[ERROR] {config_dir} not exists.")
		#sys.exit(-1)
		assert False


def modify_constraint(args, clock_period):
	'''
    Modify constraint.sdc to set clk_period to the value of args.clock_period.
	'''
	global DESIGN_DIR
	constraint_dir = os.path.join(DESIGN_DIR, 'constraint.sdc')
	tmp_dir = os.path.join(DESIGN_DIR, 'tmp.sdc')

	if os.path.isfile(constraint_dir):
		is_modified = False
		with open(constraint_dir, 'r') as original_file:
			with open(tmp_dir, 'w') as tmp_file:
				lines = original_file.readlines()
				for line in lines:
					if line.startswith('set clk_period'):
						if not line.startswith(f'set clk_period {clock_period}\n'):
							tmp_file.write(f'# {line}')
							tmp_file.write(f'set clk_period {clock_period}\n')
							is_modified = True
					else:
						tmp_file.write(line)
		if is_modified:
			utils.create_backups(constraint_dir)
			os.system(f'mv {tmp_dir} {constraint_dir}')
			print(f"Constraint file, {constraint_dir}, has modified.")
		else:
			os.system(f'rm {tmp_dir}')
	else:
		print(f"[ERROR] {constraint_dir} not exists.")
		#sys.exit(-1)
		assert False

def modify_makefile(args, clock_period):
	'''
	Create a new Makefile for the design based on Makefile_template.
	'''
	global DESIGN_DIR, FLOW_DIR, RESULTS_DIR

	custom_makefile_home = os.path.join(os.getcwd(), "Makefiles", args.platform, args.design, str(clock_period))
	if not os.path.isdir(custom_makefile_home):
		os.system(f'mkdir -p {custom_makefile_home}')
	makefile_template_dir = os.path.join(os.getcwd(), "Makefile_template")
	custom_makefile_dir = os.path.join(custom_makefile_home, "Makefile")

	#if not os.path.isfile(custom_makefile_dir):
	if True:
		FLOW_DIR = os.path.join(args.openroad_dir, 'flow')
		with open(makefile_template_dir, 'r') as template_makefile:
			with open(custom_makefile_dir, 'w') as target_makefile:
				for line in template_makefile.readlines():
					if line.startswith("DESIGN_CONFIG"):
						target_makefile.write(f'# {line}')
						#target_makefile.write(f'export DESIGN_NAME = {args.design}\n')
						target_makefile.write(f'DESIGN_CONFIG = {DESIGN_DIR}/config.mk\n')
					elif line.startswith("FLOW_HOME"):
						target_makefile.write(f'FLOW_HOME := {FLOW_DIR}\n')
					#elif line.startswith("export PLATFORM_HOME"):
					#	target_makefile.write(f'export PLATFORM = {args.platform}\n')
					#	target_makefile.write(line)
					elif line.startswith("export WORK_HOME"):
						target_makefile.write(f'WORK_HOME := {FLOW_DIR}\n')
					elif line.startswith("block"):
						target_makefile.write(f'block := $(patsubst {FLOW_DIR}/designs/$(PLATFORM)/$(DESIGN_NICKNAME)/%,%,$(dir $(3)))\n')
					elif line.startswith("export RESULTS_DIR"):
						target_makefile.write(f"export RESULTS_DIR = {RESULTS_DIR}\n")
					elif line.startswith("export FLOW_VARIANT"):
						target_makefile.write(f"export FLOW_VARIANT ?= {clock_period}\n")
					else:
						target_makefile.write(line)
		print(f"New makefile has made : {custom_makefile_dir}")
	else:
		print("Makefile exists. Skip generating Makefile.")

	return custom_makefile_home

def run_openroad(args, clock_period, makefile_home):
	'''
	Run openroad from makefile.
	'''
	global STAGE_TO_EXTRACT_WORST_SLACK
	result_dir = os.path.join(args.openroad_dir, "flow", "results", args.platform, args.design, str(clock_period))
	odb_dir = os.path.join(result_dir, f"{STAGE_TO_EXTRACT_WORST_SLACK}.odb")
	sdc_dir = os.path.join(result_dir, f"{STAGE_TO_EXTRACT_WORST_SLACK}.sdc")
	
	if os.path.isfile(odb_dir) and os.path.isfile(sdc_dir):
		print(f"{odb_dir} and {sdc_dir} exist! Skip running openroad.")
		return
	try:
		result = subprocess.run(
			["make"],
			cwd = makefile_home,
			check = True,
			text = True,
		)
	except subprocess.CalledProcessError as e:
		print(f"Error: The make command failed with exit code {e.returncode}.")
		print(f"Error output:\n{e.stderr}")
	except FileNotFoundError:
		print("Error: The 'make' command is not available. Ensure it is installed and in the PATH.")
	except Exception as e:
 		print(f"An unexpected error occurred: {e}")


	if not os.path.isdir(result_dir):
 		print(f"[ERROR] Openroad run failed.")
		#sys.exit(-1)
 		assert False



def set_global_variables(args, clock_period):
	'''
	Set global varialbes for reporting wns.
	'''
	global FLOW_DIR, RESULTS_DIR

	os.environ["SCRIPTS_DIR"] = f"{FLOW_DIR}/scripts"
	os.environ["PLATFORM_DIR"] = f"{FLOW_DIR}/platforms/{args.platform}"

	flow_variant = clock_period
	os.environ["LOG_DIR"] = f"{FLOW_DIR}/logs/{args.platform}/{args.design}/{flow_variant}"
	os.environ["OBJECTS_DIR"] = f"{FLOW_DIR}/objects/{args.platform}/{args.design}/{flow_variant}"
	os.environ["REPORTS_DIR"] = f"{FLOW_DIR}/reports/{args.platform}/{args.design}/{flow_variant}"
	os.environ["RESULTS_DIR"] = RESULTS_DIR
	
	lib_dir = f"{FLOW_DIR}/objects/{args.platform}/{args.design}/{clock_period}/lib"
	os.environ["LIB_FILES"] = " ".join([os.path.join(lib_dir, x) for x in os.listdir(lib_dir) if x.endswith(".lib")])

def report_worst_slack(args, clock_period):
	'''
	Report worst slack.
	The output will be saved to wns/${platform}/${design}/${clock_period}/worst_slack.log.
	'''
	global STAGE_TO_EXTRACT_WORST_SLACK

	worst_slack_log_home = f"worst_slack/{args.platform}/{args.design}/{clock_period}"
	if not os.path.isdir(worst_slack_log_home):
		os.system(f"mkdir -p {worst_slack_log_home}")
	worst_slack_log_dir = os.path.join(worst_slack_log_home, "worst_slack.log")

	if not os.path.isfile(worst_slack_log_dir):
		report_worst_slack_tcl_dir = '_report_worst_slack.tcl'
		with open(report_worst_slack_tcl_dir, 'w') as f:
			f.write(f"source $::env(SCRIPTS_DIR)/load.tcl\n")
			f.write(f"load_design {STAGE_TO_EXTRACT_WORST_SLACK}.odb {STAGE_TO_EXTRACT_WORST_SLACK}.sdc\n")
			f.write(f"report_worst_slack \n")
			f.write(f"exit\n")		

		openroad_run_cmd= "/root/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad -no_init"
		os.system(f"{openroad_run_cmd} {report_worst_slack_tcl_dir} | tee {worst_slack_log_dir}")
		os.system(f"rm {report_worst_slack_tcl_dir}")
	return worst_slack_log_dir

def obtain_worst_slack(args, clock_period):
	set_global_variables(args, clock_period)
	worst_slack_log_dir = report_worst_slack(args, clock_period)
	worst_slack = None
	with open(worst_slack_log_dir, 'r') as f:
		for line in f.readlines():
			info = line.split()
			if len(info) > 2 and info[0] == 'worst' and info[1] == 'slack':
				worst_slack = float(info[-1])
	if worst_slack is None:
		print(f"[ERROR] {worst_slack_log_dir} does not have worst_slack.")
		#sys.exit(-1)
		assert False
	
	return worst_slack

def write_output_log(args, clock_periods, worst_slacks):
	output_log_dir = os.path.join(os.getcwd(), "logs", args.platform, args.design)
	if not os.path.isdir(output_log_dir):
		os.system(f"mkdir -p {output_log_dir}")
	with open(os.path.join(output_log_dir, "log.log"), "w") as f:
		f.write(f"Clock periods : {str(clock_periods)}\n")
		f.write(f"Worst slacks : {str(worst_slacks)}\n")


if __name__ == "__main__":
	args = get_args()

	DESIGN_DIR = os.path.join(args.openroad_dir, 'flow', 'designs', args.platform, args.design)
	FLOW_DIR = os.path.join(args.openroad_dir, 'flow')

	modify_config(args) # Set utilization

	worst_slack = None
	clock_period = args.clock_period
	lower_bound = args.lower_bound * clock_period
	upper_bound = args.upper_bound * clock_period
	mid_point = (upper_bound + lower_bound) / 2

	print(f"Target : {lower_bound} <= worst_slack <= {upper_bound}")

	clock_periods = list()
	worst_slacks = list()

	num_iter = 0
	while worst_slack is None or not (lower_bound <= worst_slack <= upper_bound):
		RESULTS_DIR = f"{FLOW_DIR}/results/{args.platform}/{args.design}/{clock_period}"
		modify_constraint(args, clock_period) # Set clock period
		makefile_home = modify_makefile(args, clock_period)

		run_openroad(args, clock_period, makefile_home)
		worst_slack = obtain_worst_slack(args, clock_period)
		
		
		print(f"Iter: {num_iter}, Clock period: {clock_period}, Worst slack: {worst_slack}")
		clock_periods.append(clock_period)
		worst_slacks.append(worst_slack)
		write_output_log(args, clock_periods, worst_slacks)

		if worst_slack < lower_bound:
			#clock_period += (lower_bound - worst_slack)
			clock_period += (mid_point - worst_slack)
		elif worst_slack > upper_bound:
			#clock_period -= (worst_slack - upper_bound)
			clock_period -= (worst_slack - mid_point)
		
		if clock_period < 0:
			#sys.exit(-1)
			assert False

		print(f"Clock period changed to {clock_period}.")

		num_iter += 1

	print("lower_bound <= worst_slack <= upper_bound")
	print(f"{lower_bound} <= {worst_slack} <= {upper_bound}")
	print(f"Final clock period : {clock_period}")




