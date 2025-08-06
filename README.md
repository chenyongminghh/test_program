# MLU370_Test

2024/07/04
1. Update tests/pcie_link_check.py requested by LinBin, Add LSI PEX88048 50 lane, 50 port, PCI Express Gen 4.0 ExpressFabric 

2024/01/08
1. 更新Serdes测试工具为t_lpbk_serdes_34326_240108_V022_53G, X9板卡修改为1e-6
2. 更新save_mfg_log.py 修正X9和X9L的log压缩包名称

2024/01/06
1. 修改mlu370_core_voltage_adjust.py测例X9/X9L的linkdown逻辑

2023/12/26
1. 更新temp_monitor_start.py X9和X9L板卡的散热阈值为40,45;
2. 更新X9板卡的PINCS驱动release_neuware_rls4.20.24_231226_PINCS_X9

2023/12/23
1. 更新X9板卡的通用驱动和PINCS驱动，支持serdes X9的适配;

2023/12/21
1. 更新serdes工具为 t_lpbk_serdes_34326_0511_V021_53G

2023/12/14
1. 更新FW固件包，支持X9和X9L的测试；
2. 更新DVT软件包，更新通用驱动和PINCS驱动，支持X9和X9L测试；
3. 更新python测例，支持X9和X9L；

2023/11/27
1. Update mlu370_fw_20231127.tar.gz norflash tool for s8

2023/11/22
1. release-c30s-4.12.401_powerddr_NoLPW -> S8 ordered by Zhenglongyao

2023/11/21
1. Update debugtool to v0_2_7 version
2. Support S8 driver and test cases 

2022/08/17
1. Update bmc version to MLU370_BA_BMC_v118_220817.zip aupport MLU-X1001 PRO
2. update tests/bmc_vpd_check.py getting PRODUCT_PN and PRODUCT_MODEL from mfgdata file
3. update tests/bmc_vpd_update.py getting PRODUCT_PN and PRODUCT_MODEL from mfgdata file

2022/08/03
1. Update mcu version
2. Update tests/bmc_fw_check.py adding PCIE Switch Version check

2022/06/14
1. Remove write_bmc_mac in bmc_vpd_update.py after 1000pcs M8 production

2022/05/20
1. Skip "HBER Error Flag Clear" check in CAM.py request by Deheng and Jingzi

2022/05/19
1. Add write_bmc_mac in bmc_vpd_update.py requested by Zhangshuiyang

2022/05/15
1. Add setup_pci_realloc_off.py
2. Update m8burn.seq adding setup_pci_realloc_off.py

2022/05/14
1. Update bmc_vpd_update.py due to bmc-v1.17 write hdd sn issue

2022/05/12
1. Update t_lpbk_serdes_34326_0511_V021_53G 
2. Remove mlu370_check_serdes_ready.py and fec_check in m8fct.seq request by WeiLong

2022/05/10
1. Add "Clear host caches" in mlu370_load_driver.py request by LongYao

2022/04/29
1. Update to V0115-RC3
2. update PCIE_TEST_Tool_V1_1_0_x86

2022/04/26
1. Update get_bmc_fw_level_image1 amd get_bmc_fw_level_image2 parse method in IMM.py
2. Add bmc_fan_mode_get and bmc_fan_mode_set function in IMM.py
3. Add get_psu_version, get_psu_mfg and get_psu_sn in IMM.py

2022/04/25
1. Update mlu370_fw_20220425.tar.gz and all mcu to V0115-RC2.bin
2. 

2022/04/24
1. Update x4lfct.seq, move maxpower after core 0.70v restore setting
2. Correct monitor_log_file in temp_monitor_start_x4l.py

2022/04/19
1. Add mlu370_check_core_freq.py for x4fct.seq
2. Add mlu370_check_bit_ecc.py for all sequenses

2022/04/15
1. Update to mlu370_dvt_test_v1.6.3_220415.tar.gz and 4.12.3.24 driver
2. Update to X4-V0113-RC1 and x4fct.seq

2022/04/11
1. bmc_monitor_temp_fan_speed_set.py update fan speed to 60% (2U and 3U)
2. m8burnin.seq move serdes test after bmcflash operation
3. Add m8oamburnin.seq support OAM boards testing

2022/03/31
1. Add download_package_new.py in all sequenses
2. Change logic in mlu370_core_voltage_adjust.py, S4->0.72V, X4L->0.74V
3. Update CAM.py hex_core_vol = '0xA00000{:02X}'.format(int(core_voltage))
4. Add X4-V010E-RC1.bin and X4_V04_4A4ECCC6.bin
5. Update mlu370_update_mcu.py and mlu370_check_fw_version.py support specify version
6. Add mlu370_update_xdpe.py, mlu370_check_xdpe.py, x4xdpe.seq
7. Change X8 and D2 using 0.66V doing ng test

2022/03/30
1. Uppdate X4-V0114-RC1.bin and X4L-V0113-RC1.bin
2. Update mlu370_dvt_test_v1.6.3_220330.tar.gz and 4.12.3.26 driver

2022/03/28
1. Modify x4fct.seq removing cpm_count check and cpm_adjust case; change core voltage to 0.86V;
2. update pcie_link_down.py -- default gen1 boot, support --gen4 boot

2022/03/22
1. Add x4coreserver.seq and x4resnet50.seq
2. Update hostcfg.json adding 192.13/192.33/207.203

2022/03/16
1. Update mlu370_dvt_driver_nvme.py if NVME_QTY=0 skip testing
2. Update ncs loops to 10000

2022/03/15
1.更新bmc_check_nvme_presence.py 如果NVME_QTY=0，则不进行检查
2.增加temp_monitor_start_x4l.py测例删除Monitor Log
3.更新x4lfct.seq 调整进风口风扇为20%，在降压随机指令测试完成后增加maxpower测试用于相变膜融化，在fct模块的散热测试前删除Monitor Log，散热筛卡参数变更为芯片温度小于等于55
4.更新x4lburnin.seq 调整进风口风扇转速为20% 避免内部腔体温度比水温高而产生凝露

2022/03/11
1. Update serdes_tools_220309.tar.gz and t_lpbk_serdes_34326_0308_V020_53G
2. Update CAM.py check_core_voltage()
3. Update mlu370_cpm_enable.py adding -s core_voltage and X4 logic
4. Update MLU370_Debug_Tool_V0_2_5_x86
5. Update all fct.seq -- mlu370_cpm_enable.py --voltage 70

2022/03/04
1. Update dvt package to v1.6.2-0302
2. Update driver to release_neuware-c30s-4.12.3.24_ECC_53G
3. Add mlu370_core_freq_read.py and mlu370_core_freq_set.py

2022/02/22
1. Delete temp_range_check.py in x4lburnin.seq

2022/02/15
1. 更新Debugtool工具为 "MLU370_Debug_Tool_V0_2_3_x86" 版本，增加关闭CPM的功能
2. 增加测例 mlu370_cpm_close.py 实现关闭CPM功能
3. 增加测例 temp_monitor_check_x4l.py 根据monitor_log文件里面的芯片温度，进行X4L的散热筛卡
4. 更新 errorcode.json 和 description.json，增加E0095和E0096两个错误代码
5. 更新测例 temp_fan_speed_set.py，支持指定Inlet和PID的风扇转速，X4L测试时可以指定转速为0
6. 更新测例 mlu370_cpm_enable.py，将原来的减40mv和20mv参数，更新为减去30mv和10mv
7. 调整S4,X4,X8,D2板卡的FCT序列，将cpm enable变更为在0.70V Core电压的基础上进行，所有板卡固定 
8. 调整S4和X4板卡的FCT序列，将S4的Core电压由原来的抬高10mv变更为抬高20mv，X4由30mv变更为抬高40mv
9. 更新S4,X4,X8,D2板卡的FCT序列，增加关闭CPM后的0.67V随机指令测试

2022/02/10
1.  Update dvt package to mlu370_dvt_test_v1.6.0_220210.tar.gz
2.  Update driver to release-neuware-c30s-4.12.3.22_53G
3.  Update mcu firmware to V1.1.3
4.  Update isse firmware to V1.1.0

2022-01-11
Only for showing

2021-02-05
    1. Before test, copy all tool and packages from "Product Network Disk/002-MLU370/002-测试/005-自动化测试包"
    2. cd mlu370_test
    3. sudo python3 tests/setup_env.py
    4. Reboot

