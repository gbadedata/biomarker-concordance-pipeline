include { FASTQC               } from '../modules/local/fastqc/main'
include { TRIMGALORE           } from '../modules/local/trimgalore/main'
include { BWA_MEM2_INDEX       } from '../modules/local/bwa_mem2_index/main'
include { BWA_MEM2_MEM         } from '../modules/local/bwa_mem2_mem/main'
include { GATK_MARKDUPLICATES  } from '../modules/local/gatk_markduplicates/main'
include { GATK_BQSR            } from '../modules/local/gatk_bqsr/main'
include { GATK_HAPLOTYPECALLER } from '../modules/local/gatk_haplotypecaller/main'
include { GATK_GENOTYPEGVCFS   } from '../modules/local/gatk_genotypegvcfs/main'
include { VEP                  } from '../modules/local/vep/main'
include { HAPQY                } from '../modules/local/hapqy/main'


workflow GERMLINE_VARIANT_CALLING {

    take:
    samplesheet
    fasta
    fasta_fai
    fasta_dict
    bwa_index
    dbsnp
    dbsnp_tbi
    known_indels
    known_indels_tbi
    giab_truth_vcf
    giab_truth_tbi
    giab_truth_bed
    vep_cache

    main:
    ch_versions = Channel.empty()

    // QC
    FASTQC(samplesheet)
    ch_versions = ch_versions.mix(FASTQC.out.versions.first())

    // Trimming
    ch_reads = samplesheet
    if (!params.skip_trimming) {
        TRIMGALORE(samplesheet)
        ch_reads   = TRIMGALORE.out.reads
        ch_versions = ch_versions.mix(TRIMGALORE.out.versions.first())
    }

    // Index
    ch_bwa_index = bwa_index
        ? Channel.value(file(bwa_index))
        : BWA_MEM2_INDEX(fasta).index
    if (!bwa_index) ch_versions = ch_versions.mix(BWA_MEM2_INDEX.out.versions)

    // Align
    BWA_MEM2_MEM(ch_reads, ch_bwa_index, fasta)
    ch_versions = ch_versions.mix(BWA_MEM2_MEM.out.versions.first())

    // Dedup
    GATK_MARKDUPLICATES(
        BWA_MEM2_MEM.out.bam.join(BWA_MEM2_MEM.out.bai)
    )
    ch_versions = ch_versions.mix(GATK_MARKDUPLICATES.out.versions.first())

    // BQSR
    GATK_BQSR(
        GATK_MARKDUPLICATES.out.bam.join(GATK_MARKDUPLICATES.out.bai),
        fasta, fasta_fai, fasta_dict,
        dbsnp, dbsnp_tbi, known_indels, known_indels_tbi,
    )
    ch_versions = ch_versions.mix(GATK_BQSR.out.versions.first())

    // Variant calling
    GATK_HAPLOTYPECALLER(
        GATK_BQSR.out.bam.join(GATK_BQSR.out.bai),
        fasta, fasta_fai, fasta_dict, dbsnp, dbsnp_tbi,
        params.intervals ? file(params.intervals) : [],
    )
    ch_versions = ch_versions.mix(GATK_HAPLOTYPECALLER.out.versions.first())

    // Genotyping
    GATK_GENOTYPEGVCFS(
        GATK_HAPLOTYPECALLER.out.gvcf.join(GATK_HAPLOTYPECALLER.out.tbi),
        fasta, fasta_fai, fasta_dict, dbsnp, dbsnp_tbi,
    )
    ch_versions = ch_versions.mix(GATK_GENOTYPEGVCFS.out.versions.first())

    // VEP annotation
    ch_final_vcf = GATK_GENOTYPEGVCFS.out.vcf
    if (!params.skip_vep) {
        VEP(
            GATK_GENOTYPEGVCFS.out.vcf.join(GATK_GENOTYPEGVCFS.out.tbi),
            params.vep_genome, params.vep_species, params.vep_cache_version,
            params.vep_cache ? file(params.vep_cache) : [],
        )
        ch_final_vcf = VEP.out.vcf
        ch_versions  = ch_versions.mix(VEP.out.versions.first())
    }

    // Concordance benchmarking
    if (!params.skip_concordance) {
        HAPQY(
            GATK_GENOTYPEGVCFS.out.vcf.join(GATK_GENOTYPEGVCFS.out.tbi),
            giab_truth_vcf, giab_truth_tbi, giab_truth_bed,
            fasta, fasta_fai,
        )
        ch_versions = ch_versions.mix(HAPQY.out.versions.first())
    }

    emit:
    fastqc_html      = FASTQC.out.html
    final_vcf        = ch_final_vcf
    markdup_metrics  = GATK_MARKDUPLICATES.out.metrics
    hapqy_summary    = params.skip_concordance ? Channel.empty() : HAPQY.out.summary
    versions         = ch_versions
}
